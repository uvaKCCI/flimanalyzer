import http.server
import threading

import pytest
from prefect.settings import PREFECT_API_URL, temporary_settings

from flim.core import prefect_server as ps

LOCAL = f"http://{ps.DEFAULT_HOST}:{ps.DEFAULT_PORT}/api"


class FakeProcess:
    def __init__(self, exits=False):
        self.exits = exits
        self.terminated = False

    def poll(self):
        return 1 if self.exits or self.terminated else None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.terminated = True


@pytest.fixture
def no_side_effects(monkeypatch, tmp_path):
    """No real processes, sleeps or exit handlers; the environment is restored."""
    started, stops = [], []
    exit_handlers = []
    monkeypatch.setattr(ps.atexit, "register", lambda *a: exit_handlers.append(a))
    monkeypatch.setattr(ps.time, "sleep", lambda s: None)
    monkeypatch.delenv("PREFECT_API_URL", raising=False)
    monkeypatch.chdir(tmp_path)  # the server log file
    yield started, stops
    for func, *args in exit_handlers:  # as at application exit
        func(*args)


def _popen(monkeypatch, started, process):
    def popen(cmd, **kwargs):
        started.append(cmd)
        return process

    monkeypatch.setattr(ps.subprocess, "Popen", popen)


def test_configured_server_is_used(monkeypatch, no_side_effects):
    started, _ = no_side_effects
    monkeypatch.setattr(ps, "_configured_server_error", lambda: None)
    _popen(monkeypatch, started, FakeProcess())
    with temporary_settings(updates={PREFECT_API_URL: "https://prefect.example.org/api"}):
        assert ps.ensure_prefect_server() == "https://prefect.example.org/api"
    assert started == []


def test_unavailable_configured_server_falls_back_to_a_local_one(monkeypatch, no_side_effects):
    started, _ = no_side_effects
    monkeypatch.setattr(ps, "_configured_server_error", lambda: ConnectionError("down"))
    monkeypatch.setattr(ps, "_is_healthy", lambda url, timeout=2.0: url == LOCAL)
    _popen(monkeypatch, started, FakeProcess())
    with temporary_settings(updates={PREFECT_API_URL: "https://prefect.example.org/api"}):
        assert ps.ensure_prefect_server() == LOCAL
    assert started == []
    assert ps.os.environ["PREFECT_API_URL"] == LOCAL  # for subprocesses


def test_no_server_and_no_start_uses_a_temporary_server(monkeypatch, no_side_effects):
    started, _ = no_side_effects
    monkeypatch.setattr(ps, "_is_healthy", lambda url, timeout=2.0: False)
    _popen(monkeypatch, started, FakeProcess())
    with temporary_settings(restore_defaults={PREFECT_API_URL}):
        assert ps.ensure_prefect_server(start=False) is None
    assert started == []


def test_starts_a_local_server(monkeypatch, no_side_effects):
    started, _ = no_side_effects
    checks = iter([False, False, True])  # not running, starting, healthy
    monkeypatch.setattr(ps, "_is_healthy", lambda url, timeout=2.0: next(checks))
    _popen(monkeypatch, started, FakeProcess())
    with temporary_settings(restore_defaults={PREFECT_API_URL}):
        assert ps.ensure_prefect_server(port=4321) == f"http://{ps.DEFAULT_HOST}:4321/api"
    (cmd,) = started
    assert cmd[-6:] == ["server", "start", "--host", ps.DEFAULT_HOST, "--port", "4321"]


def test_server_that_exits_early_falls_back(monkeypatch, no_side_effects):
    started, _ = no_side_effects
    monkeypatch.setattr(ps, "_is_healthy", lambda url, timeout=2.0: False)
    process = FakeProcess(exits=True)
    _popen(monkeypatch, started, process)
    with temporary_settings(restore_defaults={PREFECT_API_URL}):
        assert ps.ensure_prefect_server() is None
    assert len(started) == 1


def test_server_that_cannot_be_launched_falls_back(monkeypatch, no_side_effects):
    monkeypatch.setattr(ps, "_is_healthy", lambda url, timeout=2.0: False)

    def popen(cmd, **kwargs):
        raise OSError("no prefect")

    monkeypatch.setattr(ps.subprocess, "Popen", popen)
    with temporary_settings(restore_defaults={PREFECT_API_URL}):
        assert ps.ensure_prefect_server() is None


def test_stop_terminates_a_running_server(tmp_path):
    process = FakeProcess()
    log = open(tmp_path / "server.log", "w")
    ps._stop(process, log)
    assert process.terminated and log.closed


def test_use_prefect_server_applies_the_url(monkeypatch):
    monkeypatch.setattr(ps, "ensure_prefect_server", lambda **kwargs: "http://127.0.0.1:9999/api")
    with ps.use_prefect_server() as url:
        assert url == "http://127.0.0.1:9999/api"
        assert PREFECT_API_URL.value() == url


def test_is_healthy_checks_the_health_endpoint():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/api/health" else 404)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        port = server.server_address[1]
        assert ps._is_healthy(f"http://127.0.0.1:{port}/api")
        assert not ps._is_healthy(f"http://127.0.0.1:{port}/other")
    finally:
        server.shutdown()
        server.server_close()
    assert not ps._is_healthy("http://127.0.0.1:9/api", timeout=0.5)  # nothing listening


def test_prefect_cli_of_this_environment():
    cmd = ps._prefect_cli()
    assert cmd and ("prefect" in cmd[0] or cmd[-1] == "prefect")
