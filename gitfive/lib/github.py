from bs4 import BeautifulSoup

import re
import gitfive.config

from gitfive.lib.objects import GitfiveRunner


def _api_headers(runner: GitfiveRunner):
    return {
        "Authorization": f"Bearer {runner.creds.token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }


async def create_repo(runner: GitfiveRunner, repo_name: str):
    """
    Creates the temporary repository via the GitHub REST API.
    The repo is public so its commit pages can be scraped without a
    browser session (token-only workflow).
    """
    data = {
        "name": repo_name,
        "private": False,
        "auto_init": False,
        "description": ""
    }

    req = await runner.as_client.post("https://api.github.com/user/repos", json=data, headers=_api_headers(runner))
    if req.status_code in [200, 201]:
        return True
    exit(f'Couldn\'t create repo "{repo_name}".\nResponse code : {req.status_code}\nResponse text : {req.text}')


async def delete_repo(runner: GitfiveRunner, repo_name: str):
    """
    Deletes the temporary repository via the GitHub REST API.
    Requires a token with the "delete_repo" scope.
    """
    req = await runner.as_client.delete(f"https://api.github.com/repos/{runner.creds.username}/{repo_name}", headers=_api_headers(runner))
    if req.status_code == 204:
        return True

    exit(f'Couldn\'t delete repo "{repo_name}".\nResponse code : {req.status_code}\nResponse text : {req.text}')

async def fetch_profile_name(runner: GitfiveRunner, username: str):
    """
    Uses the Github hovercards to quickly fetch the name of an username.
    """

    headers = {"X-Requested-With": "XMLHttpRequest", **runner.as_client.headers}
    req = await runner.as_client.get(f"https://github.com/users/{username}/hovercard", headers=headers)
    body = BeautifulSoup(req.text, 'html.parser')

    fields = [x.text.strip() for x in body.find("section", {"aria-label": "User login and name"}).find_all("a")]
    if len(fields) < 2:
        return False

    return fields[1]

async def get_original_branch_from_commit(runner: GitfiveRunner, commit: str, username: str, repo_name: str):
    req = await runner.as_client.get(f"https://github.com/{username}/{repo_name}/branch_commits/{commit}")
    body = BeautifulSoup(req.text, 'html.parser')
    branch = body.find("li", "branch").text.strip()
    if branch:
        return branch
    exit(f"[-] Error : branch not found for this repo and commit : {username}/{repo_name} - {commit}")

async def get_commits_history_from_blob(runner: GitfiveRunner, blob_url: str):
    res = re.compile(r"github\.com\/(.*?)\/(.*?)\/blob\/(.{40})\/(.*?)$").findall(blob_url)
    if not res:
        exit(f"[-] Error : cannot get the details from this blob_url : {blob_url}")

    username, repo_name, commit, filename = res[0]
    branch = await get_original_branch_from_commit(runner, commit, username, repo_name)
    # Keeping this function to get CNAME commits history, in the future
