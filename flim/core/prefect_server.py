"""Connects flimanalyzer to a Prefect server, starting a local one if needed."""

import atexit
import contextlib
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4200


def _is_healthy(api_url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(f"{api_url.rstrip('/')}/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _configured_server_error():
    """Checks the server of the active Prefect settings with Prefect's client, which
    also sends the API key (needed for Prefect Cloud).

    Returns:
        None if the server is healthy, otherwise the error.
    """
    from prefect.client.orchestration import get_client

    try:
        with get_client(sync_client=True) as client:
            return client.api_healthcheck()
    except Exception as err:
        return err


def _prefect_cli() -> list:
    """Command that runs the Prefect CLI of the current environment."""
    exe = Path(sys.executable).parent / ("prefect.exe" if os.name == "nt" else "prefect")
    if exe.exists():
        return [str(exe)]
    found = shutil.which("prefect")
    if found:
        return [found]
    return [sys.executable, "-m", "prefect"]


def ensure_prefect_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    start: bool = True,
    timeout: float = 60.0,
    log_file: str = "prefect-server.log",
):
    """Finds or starts the Prefect server that flows report to.

    1. If ``PREFECT_API_URL`` (environment or active Prefect profile) points to a
       responding server, that server is used.
    2. Otherwise, if a server answers at ``http://<host>:<port>/api``, it is used.
    3. Otherwise, if ``start`` is True, ``prefect server start`` is launched in the
       background and stopped again when the application exits.

    If no server can be reached, Prefect falls back to a temporary server that only
    lives as long as the application.

    Args:
        host, port: where to look for / start a local server.
        start: whether to start a server if none is running.
        timeout: seconds to wait for a started server to become healthy.
        log_file: file that receives the started server's output.

    Returns:
        str or None: API URL in use, or None for Prefect's temporary server.
    """
    from prefect.settings import PREFECT_API_URL

    configured = PREFECT_API_URL.value()
    if configured:
        error = _configured_server_error()
        if error is None:
            logging.info(f"Using Prefect server at {configured}")
            return configured
        logging.warning(
            f"Configured Prefect server at {configured} is not available ({error}),"
            " looking for a local server"
        )

    api_url = f"http://{host}:{port}/api"
    if not _is_healthy(api_url):
        if not start:
            logging.info("No Prefect server found, using a temporary server")
            return None
        cmd = _prefect_cli() + ["server", "start", "--host", host, "--port", str(port)]
        logging.info(f"Starting Prefect server: {' '.join(cmd)}")
        log = open(log_file, "a")
        try:
            process = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        except OSError as err:
            log.close()
            logging.error(f"Could not start Prefect server: {err}")
            return None
        atexit.register(_stop, process, log)
        deadline = time.monotonic() + timeout
        while not _is_healthy(api_url):
            if process.poll() is not None or time.monotonic() > deadline:
                logging.error(
                    f"Prefect server did not start, see {log_file}; using a"
                    " temporary server"
                )
                _stop(process, log)
                return None
            time.sleep(0.5)
    logging.info(f"Using Prefect server at {api_url}")
    # subprocesses (e.g. Dask workers) pick the server up from the environment
    os.environ["PREFECT_API_URL"] = api_url
    return api_url


def _stop(process, log):
    if process.poll() is None:
        logging.info("Stopping Prefect server")
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    log.close()


@contextlib.contextmanager
def use_prefect_server(**kwargs):
    """Context manager that runs its body against the server found or started by
    :func:`ensure_prefect_server` (kwargs are passed on).

    Prefect reads its settings when it is imported, so the server URL is applied
    through Prefect's settings context rather than the environment.
    """
    from prefect.settings import PREFECT_API_URL, temporary_settings

    api_url = ensure_prefect_server(**kwargs)
    if api_url:
        settings = temporary_settings(updates={PREFECT_API_URL: api_url})
    else:
        settings = temporary_settings(restore_defaults={PREFECT_API_URL})
    with settings:
        yield api_url

