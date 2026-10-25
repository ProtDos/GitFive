"""
GitFive — track down GitHub users.

Programmatic usage::

    import gitfive

    # synchronous, returns the full result as a dict
    data = gitfive.hunt("protdos")

    # async, whole result
    data = await gitfive.hunt_async("protdos")

    # async streaming, each finding as a JSON chunk
    async for chunk in gitfive.stream("protdos"):
        print(chunk["type"], chunk["data"])

See :mod:`gitfive.runner_api` for details.
"""

from gitfive.runner_api import hunt, hunt_async, stream, GitFiveError, MODES

__all__ = ["hunt", "hunt_async", "stream", "GitFiveError", "MODES"]
