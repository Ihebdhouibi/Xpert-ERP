"""Tests for the idle-killed OCR subprocess runner (cost-optimization Opt 3).

The point of the runner is to reclaim the OCR model's RAM between scans, which
is only possible by terminating the worker process. These tests prove the
worker is a separate process, is reused while warm, and is killed + respawned
after the idle window (a fresh PID after idle == the old model RAM was freed).
"""
from __future__ import annotations

import os
import time

from app.modules.ocr.process_runner import IdleProcessRunner, _worker_pid, get_runner


def test_runner_runs_in_a_separate_process():
    r = IdleProcessRunner(idle_seconds=60)
    try:
        pid = r.submit(_worker_pid)
        assert pid != os.getpid()
    finally:
        r.shutdown()


def test_runner_reuses_warm_worker():
    r = IdleProcessRunner(idle_seconds=60)
    try:
        first = r.submit(_worker_pid)
        second = r.submit(_worker_pid)
        assert first == second  # same warm process
    finally:
        r.shutdown()


def test_runner_kills_and_respawns_after_idle():
    r = IdleProcessRunner(idle_seconds=0.4)
    try:
        first = r.submit(_worker_pid)
        time.sleep(1.2)  # exceed idle window -> worker terminated, RAM reclaimed
        second = r.submit(_worker_pid)
        assert first != second  # a brand-new process proves the old one was killed
    finally:
        r.shutdown()


def test_isolation_disabled_returns_no_runner(monkeypatch):
    from app.core import config

    cfg = config.get_settings()
    monkeypatch.setattr(cfg, "cfg_ocr_process_isolation", False, raising=False)
    monkeypatch.setattr("app.core.config.get_settings", lambda: cfg)
    assert get_runner() is None


def test_isolation_enabled_returns_runner(monkeypatch):
    import app.modules.ocr.process_runner as pr
    from app.core import config

    cfg = config.get_settings()
    monkeypatch.setattr(cfg, "cfg_ocr_process_isolation", True, raising=False)
    monkeypatch.setattr(cfg, "cfg_ocr_idle_unload_seconds", 5, raising=False)
    monkeypatch.setattr("app.core.config.get_settings", lambda: cfg)
    monkeypatch.setattr(pr, "_runner", None)
    runner = get_runner()
    try:
        assert isinstance(runner, IdleProcessRunner)
    finally:
        if runner is not None:
            runner.shutdown()
        monkeypatch.setattr(pr, "_runner", None)
