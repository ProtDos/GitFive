from typing import *
import json
import os
import uuid
from pathlib import Path
from datetime import datetime

from rich.console import Console
import httpx
import trio

import gitfive.config as config


def _json_default(o: object):
    """Best-effort JSON serialization for streamed events."""
    if isinstance(o, set):
        return list(o)
    if isinstance(o, datetime):
        return f"{o.strftime('%Y/%m/%d %H:%M:%S')} (UTC)"
    return str(o)


class TMPrinter():
    """
        Print temporary text, on the same line.
    """
    def __init__(self, rc: Console=Console()):
        self.max_len = 0
        self.rc = rc

    def out(self, text: str):
        if len(text) > self.max_len:
            self.max_len = len(text)
        else:
            text += (" " * (self.max_len - len(text)))
        self.rc.print(text, end='\r')
    def clear(self):
        self.rc.print(" " * self.max_len, end="\r")

class Credentials():
    """
        Manages GitHub authentication using a personal access token (PAT).

        No username/password or browser-session login is used anymore:
        the token is read from the GITHUB_TOKEN environment variable, or
        from the token file (see config.token_path), and the account's
        username is derived from the GitHub API.
    """
    def __init__(self):
        self.username = ""
        self.token = ""

        # Client used to scrape public github.com HTML pages.
        # All scraped pages (profiles, repos, keys, the temporary public
        # repo, etc.) are public, so no authentication is required here.
        self._as_client = httpx.AsyncClient(
            headers=config.headers, timeout=config.timeout
        )

    def load_token(self, token: str = None, token_path: str = None):
        """
            Resolves the GitHub token, in this order :
              1. the `token` argument (if given),
              2. a `token_path` file argument (if given),
              3. the GITHUB_TOKEN environment variable,
              4. the default token file (config.token_path).
        """
        if token:
            self.token = token.strip()
            return

        resolved = ""
        if token_path:
            p = Path(token_path).expanduser()
            if not p.is_file():
                exit(f"[-] Token file not found : {token_path}")
            resolved = self._parse_token_file(p.read_text(encoding="utf-8"))
        else:
            resolved = os.environ.get("GITHUB_TOKEN", "").strip()
            if not resolved:
                p = Path(config.token_path).expanduser()
                if p.is_file():
                    resolved = self._parse_token_file(p.read_text(encoding="utf-8"))
        if not resolved:
            exit("[-] No GitHub token found.\n"
                 "    Pass a token, set the GITHUB_TOKEN environment variable, or "
                 f"save the token in {config.token_path}.")
        self.token = resolved

    @staticmethod
    def _parse_token_file(content: str) -> str:
        """
            Accepts either a bare token or an env-style file containing a
            GITHUB_TOKEN=... line, and returns the token value.
        """
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                if key.strip().upper() in ("GITHUB_TOKEN", "TOKEN"):
                    return value.strip().strip('"').strip("'")
            else:
                return line.strip('"').strip("'")
        return ""

    def check_token(self):
        """
            Validates the token against the GitHub API, derives the
            authenticated username and checks for the required scopes.
        """
        print("Checking API token validity...")
        headers = {"Authorization": f"Bearer {self.token}"}
        req = httpx.get("https://api.github.com/user", headers=headers)
        if req.status_code == 401:
            exit("[-] Token seems invalid.")
        if req.status_code != 200:
            exit(f"[-] GitHub API is returning an unexpected status code ({req.status_code}). Is your token correct ?")

        data = json.loads(req.text)
        self.username = data["login"]

        raw_scopes = req.headers.get("x-oauth-scopes")
        if raw_scopes is not None:
            from gitfive.lib.utils import humanize_list
            requirements = {"repo", "delete_repo"}
            scopes = [x.strip() for x in raw_scopes.split(",") if x.strip()]
            missing_scopes = requirements - set(scopes)
            if missing_scopes:
                exit(f"[-] Token is missing required scopes : {humanize_list(sorted(missing_scopes))} "
                     f"(current scopes : {humanize_list(scopes) if scopes else 'none'}).")
            print(f"[+] Token valid ! (scopes : {humanize_list(sorted(requirements))})")

            excessive_scopes = set(scopes) - requirements
            if excessive_scopes:
                print(f"[!] Your token has excessive scopes (scopes : {humanize_list(sorted(excessive_scopes))}).")
                print("These scopes are not needed by GitFive, so be sure to keep it secure, or generate a new one.")
        else:
            # Fine-grained tokens don't expose the x-oauth-scopes header.
            print("[!] Couldn't read token scopes (fine-grained token?).")
            print("    Make sure it can create and delete repositories, otherwise GitFive will fail.")

        print(f"[+] Authenticated as {self.username} !\n")


class TargetEncoder(json.JSONEncoder):
    """
        Converts non-default types when exporting to JSON.
    """
    def default(self, o: object) -> dict:
        if isinstance(o, Target):
            return o.__dict__
        elif isinstance(o, set):
            return list(o)
        elif isinstance(o, datetime):
            return f"{o.strftime('%Y/%m/%d %H:%M:%S')} (UTC)"

class Target():
    """
        Manages all the target's data during GitFive's run.
    """
    def __init__(self):
        self.username = ""
        self.name = ""
        self.id = ""
        self.is_site_admin = False
        self.is_hireable = False
        self.company = ""
        self.blog = ""
        self.location = ""
        self.bio = ""
        self.twitter = ""
        self.nb_public_repos = 0
        self.nb_followers = 0
        self.nb_following = 0
        self.created_at: datetime = None
        self.updated_at: datetime = None
        self.avatar_url = ""
        self.is_default_avatar = True
        self.nb_ext_contribs = 0

        self.potential_friends: Dict[str, Dict[str, int|bool]] = {}
        self.repos: List[Dict[str, any]] = []
        self.languages_stats: Dict[str, float] = {}
        self.orgs: List[Dict[str, any]]

        self.usernames = set()
        self.fullnames = set()
        self.domains = set()

        self.ssh_keys: List[str] = []

        self.all_contribs: Dict[str, Dict[str, Dict[str, Dict[str, Set[str]]]]] = {}
        self.ext_contribs: Dict[str, Dict[str, Dict[str, Dict[str, Set[str]]]]] = {}
        self.internal_contribs: Dict[str, Dict[str, Dict[str, Dict[str, Dict[str, Set[str]]]]]] = {"all": {}, "no_github": {}}
        self.usernames_history: Dict[str, Dict[str, Dict[str, Dict[str, Set[str]]]]] = {}
        self.near_names: Dict[str, Dict[str, Dict[str, Dict[str, Dict[str, Dict[str, Set[str]]]]]]] = {}

        self.emails = set()
        self.generated_emails = set()
        self.registered_emails: Dict[str, any] = {}

    def export_json(self):
        return json.dumps(self, cls=TargetEncoder, indent=4)

    @property
    def _possible_names(self) -> Set[str]:
        return {x.lower() for x in self.usernames.union(self.fullnames)}

    def _add_name(self, name: str):
        if name:
            if " " in name:
                self.fullnames.add(name)
            else:
                self.usernames.add(name)

    def _scrape(self, data: Dict[str, any]):
        self.username = data["login"] # We use the username from this field because it can have uppercase letters
        from gitfive.lib.utils import unicode_patch
        self.name = unicode_patch(data["name"]) if data["name"] else ""
        self.id = data["id"]
        self.type = data["type"]
        self.is_site_admin = data["site_admin"]
        self.hireable = data["hireable"]
        self.company = data["company"]
        self.blog = data["blog"]
        self.location = data["location"]
        self.bio = data["bio"]
        self.twitter = data["twitter_username"]
        self.nb_public_repos = data["public_repos"]
        self.nb_followers = data["followers"]
        self.nb_following = data["following"]
        self.created_at = datetime.strptime(data["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        self.updated_at = datetime.strptime(data["updated_at"], "%Y-%m-%dT%H:%M:%SZ")

        # Profile pic
        from gitfive.lib.utils import get_image_hash, fetch_img
        self.avatar_url = data["avatar_url"].split('?')[0]
        avatar = fetch_img(self.avatar_url)
        avatar_hash = get_image_hash(avatar)

        identicon = fetch_img(f'https://github.com/identicons/{self.username}.png')
        identicon_hash = get_image_hash(identicon)

        if avatar_hash != identicon_hash:
            self.is_default_avatar = False

class GitfiveRunner():
    """
        Centralizes common informations and functions needed during GitFive's run.
    """
    def __init__(self):
        from gitfive.lib.api import APIInterface
        self.rc = Console(highlight=False) # To print with colors
        self.tmprinter = TMPrinter(self.rc)
        self.creds = Credentials()
        self.target: Target = Target()
        self.as_client = self.creds._as_client
        self.api: APIInterface = None

        # Per-run working directory, unique to this runner, so multiple hunts
        # can run in parallel without sharing (and deleting) each other's files.
        self.run_id = uuid.uuid4().hex
        self.run_dir: Path = Path.home() / ".malfrats" / "gitfive" / ".tmp" / self.run_id

        self.limiters: Dict[str, trio.CapacityLimiter] = {
            "pea_repos": trio.CapacityLimiter(10),
            "pea_repos_search": trio.CapacityLimiter(10),
            "pea_followers": trio.CapacityLimiter(10),
            "social_follows": trio.CapacityLimiter(50),
            "repos_list": trio.CapacityLimiter(50),
            "commits_scrape": trio.CapacityLimiter(50),
            "commits_fetch_avatar": trio.CapacityLimiter(1), # https://github.com/mxrch/GitFive/issues/3#issuecomment-1321260050
            "orgs_list": trio.CapacityLimiter(50)
        }

        self.xray_near_iteration = 0
        self.emails_accounts: Dict[str, Dict[str, any]] = {}
        self.shown_emails = set()
        self.shown_near_names = set()

        self.spoofed_emails = set()
        self.analyzed_usernames = set()

        # Optional callback used by the programmatic API to stream structured
        # events. When set, it receives dicts shaped as {"type": str, "data": any}.
        self._emit: Callable[[Dict[str, any]], None] = None

    def cleanup(self):
        """
            Removes only THIS run's working directory, leaving concurrent
            hunts' directories untouched.
        """
        from shutil import rmtree
        from gitfive.lib.utils import change_permissions
        if self.run_dir.is_dir():
            try:
                change_permissions(self.run_dir)
            except Exception:
                pass
            rmtree(self.run_dir, ignore_errors=True)

    def emit(self, event_type: str, data: any = None):
        """
            Pushes a structured, JSON-serializable event to the registered
            streaming callback (if any). No-op in the normal CLI flow.
        """
        if self._emit is None:
            return
        payload = json.loads(json.dumps(data, default=_json_default)) if data is not None else None
        self._emit({"type": event_type, "data": payload})

    async def login(self, token: str = None, token_path: str = None):
        """
            Loads the GitHub token, validates it and loads the API Interface.
        """
        from gitfive.lib.api import APIInterface
        self.creds.load_token(token=token, token_path=token_path)
        self.creds.check_token()
        self.api = APIInterface(self.creds)
