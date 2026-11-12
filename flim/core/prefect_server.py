"""Connects flimanalyzer to a Prefect server, starting a local one if needed."""

import atexit
import contextlib
import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import IO, Any

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4200

# the server of the active `use_prefect_server`: its arguments, the API URL in use and
# the API URL configured before (environment or Prefect profile)
_session: dict = {}
_session_lock = threading.Lock()


def _is_healthy(api_url: str, timeout: float = 2.0) -> bool:
    """Return whether the health endpoint of `api_url` answers with status 200."""
    try:
        with urllib.request.urlopen(f"{api_url.rstrip('/')}/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _configured_server_error() -> Exception | None:
    """Check the server of the active Prefect settings with Prefect's client.

    The client also sends the API key, which Prefect Cloud requires.

    Returns:
        None if the server is healthy, otherwise the error.
    """
    from prefect.client.orchestration import get_client

    try:
        with get_client(sync_client=True) as client:
            return client.api_healthcheck()
    except Exception as err:
        return err


def _prefect_cli() -> list[str]:
    """Return the command that runs the Prefect CLI of the current environment."""
    exe = Path(sys.executable).parent / ("prefect.exe" if os.name == "nt" else "prefect")
    if exe.exists():
        return [str(exe)]
    found = shutil.which("prefect")
    if found:
        return [found]
    return [sys.executable, "-m", "prefect"]


class PrefectServerError(RuntimeError):
    """No Prefect server could be found or started."""


def _free_port(host: str) -> int:
    """Return a port on `host` that nothing listens on at the moment."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def _start_server(
    host: str, port: int, timeout: float, log_file: str | os.PathLike
) -> str | None:
    """Start `prefect server start` on `host:port` and wait until it is healthy.

    Returns:
        The server's API URL, or None if it did not start (the process is then
        stopped).
    """
    api_url = f"http://{host}:{port}/api"
    cmd = _prefect_cli() + ["server", "start", "--host", host, "--port", str(port)]
    logger.info(f"Starting Prefect server: {' '.join(cmd)}")
    log = open(log_file, "a")
    try:
        process = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
    except OSError as err:
        log.close()
        logger.warning(f"Could not start Prefect server: {err}")
        return None
    deadline = time.monotonic() + timeout
    while not _is_healthy(api_url):
        if process.poll() is not None or time.monotonic() > deadline:
            logger.warning(f"Prefect server on port {port} did not start, see {log_file}")
            _stop(process, log)
            return None
        time.sleep(0.5)
    atexit.register(_stop, process, log)
    return api_url


def ensure_prefect_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    start: bool = True,
    timeout: float = 60.0,
    log_file: str | os.PathLike = "prefect-server.log",
) -> str | None:
    """Find or start the Prefect server that all flows of this process report to.

    1. If `PREFECT_API_URL` (environment or active Prefect profile) points to a
       responding server, that server is used.
    2. Otherwise, if a server answers at `http://<host>:<port>/api`, it is used.
    3. Otherwise, if `start` is True, `prefect server start` is launched on
       `port` in the background, and stopped again when the process exits.
    4. If that server does not start (e.g. the port is taken), it is launched on a
       free port instead.

    With `start` False and no server found, Prefect starts a temporary server for
    each flow run. The URL of a local server (2 to 4) is also set as the environment
    variable `PREFECT_API_URL`, for subprocesses such as Dask workers.

    Args:
        host: The host where a local server is looked for or started. Defaults to
            `127.0.0.1`.
        port: The port where a local server is looked for or started. Defaults to
            4200.
        start: Whether to start a server if none is running.
        timeout: Seconds to wait for a started server to become healthy.
        log_file: The file that receives the started server's output; output is
            appended.

    Returns:
        The API URL in use, or None for Prefect's temporary servers.

    Raises:
        PrefectServerError: If `start` is True and no server could be started.
    """
    from prefect.settings import PREFECT_API_URL

    configured = PREFECT_API_URL.value()
    if configured:
        error = _configured_server_error()
        if error is None:
            logger.info(f"Using Prefect server at {configured}")
            return configured
        logger.warning(
            f"Configured Prefect server at {configured} is not available ({error}),"
            " looking for a local server"
        )

    api_url = f"http://{host}:{port}/api"
    if not _is_healthy(api_url):
        if not start:
            logger.info("No Prefect server found, using temporary servers")
            return None
        api_url = _start_server(host, port, timeout, log_file)
        if api_url is None:
            api_url = _start_server(host, _free_port(host), timeout, log_file)
        if api_url is None:
            raise PrefectServerError(
                f"No Prefect server could be started, see {os.path.abspath(log_file)}."
                " Configure a Prefect server in a Prefect profile, or start without"
                " one with --no-prefect-server."
            )
    logger.info(f"Using Prefect server at {api_url}")
    # subprocesses (e.g. Dask workers) pick the server up from the environment
    os.environ["PREFECT_API_URL"] = api_url
    return api_url


def _stop(process: subprocess.Popen, log: IO[str]) -> None:
    """Stop the server process (killed after 10 s if needed) and close its log."""
    if process.poll() is None:
        logger.info("Stopping Prefect server")
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    log.close()


def _settings(api_url: str | None) -> contextlib.AbstractContextManager[Any]:
    """Return a Prefect settings context that sets the API URL, or removes it if None."""
    from prefect.settings import PREFECT_API_URL, temporary_settings

    if api_url:
        return temporary_settings(updates={PREFECT_API_URL: api_url})
    return temporary_settings(restore_defaults={PREFECT_API_URL})


@contextlib.contextmanager
def use_prefect_server(**kwargs: Any) -> Iterator[str | None]:
    """Run the body against the server found or started by `ensure_prefect_server`.

    Prefect reads its settings when it is imported, so the server URL is applied
    through Prefect's settings context rather than the environment. That context
    belongs to the current thread: a thread started inside the body has to run in a
    copy of it (`contextvars.copy_context().run`), or its flows use the settings
    Prefect read at import. Each flow run inside the body should run in
    `checked_prefect_server`.

    Args:
        **kwargs: The arguments of `ensure_prefect_server`; they are also used when
            `checked_prefect_server` finds or starts a server again.

    Yields:
        The API URL in use, or None for Prefect's temporary servers.

    Raises:
        PrefectServerError: If no server could be found or started.
    """
    from prefect.settings import PREFECT_API_URL

    configured = PREFECT_API_URL.value()
    api_url = ensure_prefect_server(**kwargs)
    with _session_lock:
        _session.update(kwargs=kwargs, url=api_url, configured=configured)
    try:
        with _settings(api_url):
            yield api_url
    finally:
        with _session_lock:
            _session.clear()


def _available(api_url: str) -> bool:
    """Return whether the server at `api_url` answers.

    The health endpoint is tried first; Prefect's client, which also sends the API
    key, is used if that fails (needed for Prefect Cloud).
    """
    if _is_healthy(api_url):
        return True
    with _settings(api_url):
        return _configured_server_error() is None


@contextlib.contextmanager
def checked_prefect_server() -> Iterator[str | None]:
    """Context manager for one flow run inside `use_prefect_server`.

    Before the run, it checks that the server of the session still answers. A local
    server can stop while the process runs, for example when another flimanalyzer
    process that started it exits. In that case a server is found or started again
    as in `ensure_prefect_server`, with the arguments given to `use_prefect_server`,
    and used for this and later runs. Outside `use_prefect_server`, or if the session
    uses Prefect's temporary servers, no server is checked.

    Yields:
        The API URL the run uses, or None for Prefect's temporary servers or
        outside `use_prefect_server`.

    Raises:
        PrefectServerError: If the server is gone and no server could be started.
    """
    with _session_lock:
        active = "url" in _session
        api_url = _session.get("url")
        if api_url and not _available(api_url):
            logger.warning(
                f"Prefect server at {api_url} is no longer available,"
                " finding or starting a server again"
            )
            # searched as at the start of the session
            with _settings(_session["configured"]):
                api_url = ensure_prefect_server(**_session["kwargs"])
            _session["url"] = api_url
    if not active:
        yield None
        return
    # the URL of the session: a server started again by an earlier run replaces the
    # one in the context of `use_prefect_server`
    with _settings(api_url):
        yield api_url
