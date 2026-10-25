"""
Programmatic API for GitFive.

Import GitFive as a module and run a hunt either **synchronously** (blocking,
returns the full result as JSON) or **asynchronously with streaming** (yields
each new piece of information as a JSON-serializable chunk as it is found).

Authentication is token-only : the GitHub token is read from the `token`
argument, a `token_path` file, the `GITHUB_TOKEN` environment variable, or the
default token file (``~/.github.token``), in that order.

Examples
--------
Synchronous — wait for the whole response, get a dict back::

    import gitfive
    data = gitfive.hunt("protdos")                  # mode defaults to "user"

Async — whole response::

    data = await gitfive.hunt_async("protdos")

Async — streaming, each finding as a chunk::

    async for chunk in gitfive.stream("protdos"):
        print(chunk["type"], chunk["data"])

Every chunk is a dict ``{"type": str, "data": <json>}``. The stream always ends
with a ``{"type": "result", "data": <full result>}`` chunk (or a
``{"type": "error", ...}`` chunk on failure).

`mode` is one of ``"user"``, ``"email"``, ``"emails"`` or ``"light"``. For the
``"emails"`` mode, `target` is the path to a file containing one email per line.

The async entry points run GitFive's internal trio loop in a worker thread, so
they can be awaited from either an asyncio or a trio event loop.
"""

import json
import queue
import threading
from typing import Any, AsyncIterator, Callable, Dict, Optional

import trio

from gitfive.lib.objects import GitfiveRunner


MODES = ("user", "email", "emails", "light")

_SENTINEL = object()


class GitFiveError(Exception):
    """Raised when a hunt fails (invalid token, user not found, etc.)."""


def _exit_message(exc: SystemExit) -> str:
    code = exc.code
    if code is None:
        return "GitFive exited."
    return str(code).strip()


def _flatten(exc: BaseException) -> str:
    if isinstance(exc, SystemExit):
        return _exit_message(exc)
    if isinstance(exc, BaseExceptionGroup):
        return "; ".join(_flatten(e) for e in exc.exceptions)
    return str(exc) or exc.__class__.__name__


async def _drive(target: str, mode: str, token: Optional[str],
                 token_path: Optional[str], emit: Optional[Callable]) -> Dict[str, Any]:
    if mode not in MODES:
        raise GitFiveError(f"Unknown mode {mode!r}. Valid modes : {', '.join(MODES)}.")

    runner = GitfiveRunner()
    runner._emit = emit
    await runner.login(token=token, token_path=token_path)

    if mode == "user":
        from gitfive.modules import username_mod
        await username_mod.hunt(target, "", runner)
        return json.loads(runner.target.export_json())

    if mode == "email":
        from gitfive.modules import email_mod
        username = await email_mod.hunt(target, "", runner)
        if username:
            return json.loads(runner.target.export_json())
        return {"email": target, "found": False}

    if mode == "emails":
        from gitfive.modules import emails_mod
        accounts = await emails_mod.hunt(target, "", "", runner)
        return {"accounts": accounts or {}}

    # mode == "light"
    from gitfive.modules import light_mod
    emails = await light_mod.hunt(target, runner)
    return {"username": target, "emails": emails or []}


def _run_blocking(target: str, mode: str, token: Optional[str],
                  token_path: Optional[str], emit: Optional[Callable]) -> Dict[str, Any]:
    """Runs the whole hunt in a fresh trio loop and returns the result."""
    async def _main():
        return await _drive(target, mode, token, token_path, emit)

    try:
        return trio.run(_main)
    except GitFiveError:
        raise
    except KeyboardInterrupt:
        raise
    except BaseException as e:  # SystemExit / ExceptionGroup / anything else
        raise GitFiveError(_flatten(e)) from e


def hunt(target: str, mode: str = "user", *,
         token: Optional[str] = None, token_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Synchronous hunt. Blocks until finished and returns the full result as a
    dict (JSON-serializable). Call this from plain synchronous code — not from
    inside a running event loop (use :func:`hunt_async` there).
    """
    return _run_blocking(target, mode, token, token_path, emit=None)


async def hunt_async(target: str, mode: str = "user", *,
                     token: Optional[str] = None, token_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Asynchronous hunt that waits for the whole response and returns it as a
    dict. Awaitable from an asyncio or trio event loop.
    """
    import anyio
    return await anyio.to_thread.run_sync(
        _run_blocking, target, mode, token, token_path, None
    )


async def stream(target: str, mode: str = "user", *,
                 token: Optional[str] = None,
                 token_path: Optional[str] = None) -> AsyncIterator[Dict[str, Any]]:
    """
    Asynchronous streaming hunt. Yields each new piece of information as a
    JSON-serializable chunk ``{"type": str, "data": <json>}`` as soon as it is
    found, then a final ``{"type": "result", "data": <full result>}`` chunk.
    On failure, yields a ``{"type": "error", "data": {"message": ...}}`` chunk.

    Awaitable from an asyncio or trio event loop.
    """
    import anyio

    q: "queue.Queue" = queue.Queue()

    def worker():
        try:
            result = _run_blocking(target, mode, token, token_path, emit=q.put)
            q.put({"type": "result", "data": result})
        except GitFiveError as e:
            q.put({"type": "error", "data": {"message": str(e)}})
        except BaseException as e:
            q.put({"type": "error", "data": {"message": _flatten(e)}})
        finally:
            q.put(_SENTINEL)

    thread = threading.Thread(target=worker, name="gitfive-hunt", daemon=True)
    thread.start()

    while True:
        item = await anyio.to_thread.run_sync(q.get)
        if item is _SENTINEL:
            break
        yield item
