![](assets/banner.png)

<br>

![Python minimum version](https://img.shields.io/badge/Python-3.10%2B-brightgreen)

#### 🐍 Now Python 3.13 compatible !

# Description

GitFive is an OSINT tool to investigate GitHub profiles.

Main features :
- Usernames / names history
- Usernames / names variations
- Email address to GitHub account
- Find GitHub's accounts from a list of email addresses
- Lists identities used by the target
- Clones and analyze every target's repos
- Highlights emails tied to GitHub's target account
- Finds local identities (UPNs, ex : jeanpierre@My-Computer.local)
- Finds potential secondary GitHub accounts
- Don't need repos to work (but better)
- Generates every possible email address combinations and looks for matchs
- Dumps SSH public keys
- JSON export

Optimizations :
- Very low API consumption, stays under the rate-limit
- Multi-processing tasks (bypassing Python's GIL)
- Async scraping

# Workflow
**Click [here](https://raw.githubusercontent.com/mxrch/GitFive/master/assets/workflow.png) for a full view**

<br>

![](assets/workflow.png)

# Requirements
- Git
- Python >= 3.10

# Installation

```bash
$ pip3 install pipx
$ pipx ensurepath
$ pipx install gitfive
```
It will automatically use venvs to avoid dependency conflicts with other projects.

# Usage
GitFive authenticates with a **GitHub personal access token** (scopes `repo` and `delete_repo`). No username/password or browser login is used.

Provide the token in any of these ways (checked in this order):
1. the `token` / `token_path` argument of the Python API (see below),
2. the `GITHUB_TOKEN` environment variable,
3. the token file `~/.github.token` (a bare token, or a `GITHUB_TOKEN=...` line).

Check that your token works :
```bash
$ gitfive login
```

Then, profit :
```bash
usage: gitfive [-h] {login,user,email,emails,light} ...

positional arguments:
  {login,user,email,emails,light}
    login               Let GitFive authenticate to GitHub.
    user                Track down a GitHub user by its username.
    email               Track down a GitHub user by its email address.
    emails              Find GitHub usernames of a given list of email addresses.
    light               Quickly find emails addresses from a GitHub username.

options:
  -h, --help            show this help message and exit
```


*PS : plz avoid testing on torvalds or other authors of repos with 1 million commits*

📄 You can also use --json with user and email modules to export in JSON ! Example :

```bash
$ gitfive user mxrch --json mxrch_data.json
```

# Use as a Python module

GitFive can be imported and run programmatically. You get the data back as JSON,
either synchronously (wait for the whole response) or asynchronously with
streaming (each new finding is yielded as a chunk as soon as it is found).

```python
import gitfive

# Synchronous — blocks and returns the full result as a dict
data = gitfive.hunt("mxrch")                      # mode defaults to "user"
```

```python
import asyncio
import gitfive

# Async — wait for the whole response
data = asyncio.run(gitfive.hunt_async("mxrch"))

# Async — stream each new piece of information as a JSON chunk
async def run():
    async for chunk in gitfive.stream("mxrch"):
        print(chunk["type"], chunk["data"])
        # chunk types: profile, external_contributions, ssh_keys, gists,
        # repositories, close_friends, organizations, identities, emails,
        # and a final "result" chunk (or an "error" chunk on failure).

asyncio.run(run())
```

- **`mode`** — one of `"user"`, `"email"`, `"emails"`, `"light"`. For `"emails"`, `target` is the path to a file of email addresses (one per line).
- **Token** — pass `token="ghp_..."` or `token_path="/path/to/token"`, otherwise `GITHUB_TOKEN` / `~/.github.token` are used.
- The async entry points run GitFive's internal loop in a worker thread, so they can be awaited from either an **asyncio** or a **trio** event loop.

```python
# Override the token explicitly, pick a different mode
data = gitfive.hunt("someone@example.com", mode="email", token="ghp_xxx")
```

**Have fun 🥰💞**

## Video demo

https://github.com/mxrch/GitFive/assets/17338428/28a22d30-f651-483f-84e8-7fc6e00b831f

## Obvious disclaimer

This tool is for educational purposes only, I am not responsible for its use.

### Less obvious disclaimer

The use of this tool in an automated paid service / software is strictly forbidden without my personal agreement.\
Please use it only in personal, criminal investigations, or open-source projects.

## Thanks

- [novitae](https://github.com/novitae) for being my Python colleague
- [rayanlecat](https://twitter.com/rayanlecat), [ABH](https://twitter.com/ABHsec), [22sh](https://twitter.com/0x22sh), [BlackWasp](https://twitter.com/BlWasp_), [Tartofraise](https://twitter.com/_Tartofraise), [mpgn](https://twitter.com/mpgn_x64), [M3SS](https://twitter.com/0x4D335353) and [n1nj4sec](https://twitter.com/n1nj4sec) for the beta test
- The HideAndSec team 💗 (blog : https://hideandsec.sh)

## Sponsors

Thanks to these awesome people for supporting me !

<!-- sponsors --><a href="https://github.com/BlWasp"><img src="https://github.com/BlWasp.png" width="50px" alt="BlWasp" /></a>&nbsp;&nbsp;<a href="https://github.com/gingeleski"><img src="https://github.com/gingeleski.png" width="50px" alt="gingeleski" /></a>&nbsp;&nbsp;<!-- sponsors -->

\
You like my work ?\
[Sponsor me](https://github.com/sponsors/mxrch) on GitHub ! 🤗
