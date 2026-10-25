import trio
from alive_progress import alive_bar


from gitfive.lib.utils import *
from gitfive.lib import github


async def fetch_avatar(runner: GitfiveRunner, email: str, avatar_link: str, username: str,
                        out: Dict[str, str|bool], check_only: bool):
    async with runner.limiters["commits_fetch_avatar"]:
        is_target = (username.lower() == runner.target.username.lower())
        if check_only:
            if is_target:
                runner.rc.print(f"[+] [Target's email] 🐱 {email} -> @{username}", style="cyan")

            out[email] = {
                "avatar": avatar_link,
                "username": username,
                "is_target": is_target
            }
        else:
            full_name = await github.fetch_profile_name(runner, username)
            _name_str = ""
            if full_name:
                _name_str = f" [{full_name}]"

            if is_target:
                runner.rc.print(f"[+] [TARGET FOUND] 🐱 {email} -> @{username}{_name_str}", style="green bold")
            else:
                runner.rc.print(f"[+] 🐱 {email} -> @{username}{_name_str}")

            out[email] = {
                "avatar": avatar_link,
                "full_name": full_name,
                "username": username,
                "is_target": is_target
            }

async def scrape(runner: GitfiveRunner, repo_name: str, emails_index: Dict[str, str], check_only=False):
    """
    Lists the mirage repo's commits through the GitHub REST API and resolves,
    for each spoofed email, the GitHub account it is linked to.

    Each mirage commit carries the spoofed email as its *author* (see metamon),
    so the API's resolved `author.login` reveals the owning account — no HTML
    scraping or browser session required.
    """
    out = {}
    owner = runner.creds.username
    valid_emails = set(emails_index.values())

    _, total = await get_commits_count(runner, repo_url=f"https://github.com/{owner}/{repo_name}")
    if not total:
        exit("Empty repository.")

    with alive_bar(total, receipt=False, enrich_print=False, title="Fetching committers...") as bar:
        async with trio.open_nursery() as nursery:
            page = 1
            while True:
                data = await runner.api.query(
                    f"/repos/{owner}/{repo_name}/commits?sha=mirage&per_page=100&page={page}",
                    connection_type="authenticated"
                )
                if not isinstance(data, list) or not data:
                    break

                for commit in data:
                    bar()
                    email = commit.get("commit", {}).get("author", {}).get("email", "")
                    if email not in valid_emails:
                        continue  # genesis / merge commits

                    gh_user = commit.get("author")  # resolved GitHub account, or None
                    if not gh_user or not gh_user.get("login"):
                        continue

                    nursery.start_soon(
                        fetch_avatar, runner, email,
                        gh_user.get("avatar_url", ""), gh_user["login"], out, check_only
                    )

                if len(data) < 100:
                    break
                page += 1

    return out
