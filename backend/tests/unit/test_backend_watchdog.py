"""Windows watchdog acceptance tests for Phase D #15."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

_POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
_REPO_ROOT = Path(__file__).resolve().parents[3]
_WATCHDOG = _REPO_ROOT / "scripts/services/watch_truthnet_backend.ps1"
_REGISTER = _REPO_ROOT / "scripts/services/register_truthnet_backend_watchdog.ps1"
_TRUTHNET_PYTHON = Path("D:/anaconda/envs/truthnet/python.exe")

pytestmark = pytest.mark.skipif(
    not _POWERSHELL or not _TRUTHNET_PYTHON.exists(),
    reason="Windows PowerShell and the truthnet Python runtime are required",
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run_watchdog(log_dir: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(_POWERSHELL),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_WATCHDOG),
            "-LogDirectory",
            str(log_dir),
            *arguments,
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8-sig",
        timeout=30,
        check=False,
    )


def _events(log_dir: Path) -> list[dict]:
    lines = (log_dir / "watchdog.jsonl").read_text(encoding="utf-8-sig").splitlines()
    return [json.loads(line) for line in lines]


class _OtherServiceHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        body = b'{"service":"other"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def test_watchdog_check_reports_free_port(tmp_path):
    result = _run_watchdog(
        tmp_path,
        "-Port",
        str(_free_port()),
        "-CheckOnly",
    )

    assert result.returncode == 0, result.stderr
    assert _events(tmp_path)[-1]["event"] == "port_free"


def test_watchdog_reports_non_truthnet_port_conflict(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _OtherServiceHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = _run_watchdog(
            tmp_path,
            "-Port",
            str(server.server_port),
            "-CheckOnly",
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.returncode == 2, result.stderr
    event = _events(tmp_path)[-1]
    assert event["event"] == "port_conflict"
    assert "non-TruthNet" in event["reason"]


def test_watchdog_logs_startup_failure(tmp_path):
    result = _run_watchdog(
        tmp_path,
        "-Port",
        str(_free_port()),
        "-PythonPath",
        str(tmp_path / "missing-python.exe"),
    )

    assert result.returncode == 3, result.stderr
    event = _events(tmp_path)[-1]
    assert event["event"] == "startup_failed"
    assert event["reason"] == "python executable not found"


def test_watchdog_records_exit_code_and_restart_count(tmp_path):
    result = _run_watchdog(
        tmp_path,
        "-Port",
        str(_free_port()),
        "-PythonPath",
        str(_TRUTHNET_PYTHON),
        "-BackendDirectory",
        str(_REPO_ROOT / "backend"),
        "-AppModule",
        "missing.module:app",
        "-StartupProbeSeconds",
        "0",
        "-RestartDelaySeconds",
        "0",
        "-MaxRestarts",
        "1",
    )

    events = _events(tmp_path)
    exited = next(event for event in events if event["event"] == "process_exited")
    state = json.loads(
        (tmp_path / "watchdog-state.json").read_text(encoding="utf-8-sig")
    )
    assert result.returncode != 0
    assert exited["exit_code"] == result.returncode
    assert exited["restart_count"] == 1
    assert state["restart_count"] == 1
    assert events[-1]["event"] == "watchdog_stopped"


def test_task_registration_whatif_has_no_side_effects():
    result = subprocess.run(
        [
            str(_POWERSHELL),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_REGISTER),
            "-PythonPath",
            str(_TRUTHNET_PYTHON),
            "-Port",
            str(_free_port()),
            "-WhatIf",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8-sig",
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
