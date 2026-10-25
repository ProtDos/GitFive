from gitfive.lib.objects import GitfiveRunner


async def check_and_login(clean=False):
    """
    Validates the GitHub token used by GitFive.

    Authentication is token-only : the token is read from the GITHUB_TOKEN
    environment variable, or from the token file (config.token_path).
    There are no credentials or session files to manage anymore, so the
    --clean flag is kept only for backward compatibility.
    """
    if clean:
        print("[+] Nothing to clean : GitFive is token-only and stores no credentials locally.")
        return

    runner = GitfiveRunner()
    await runner.login()
    print("[+] Token is valid and ready to use !")
