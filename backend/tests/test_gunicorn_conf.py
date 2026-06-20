"""Tests for the gunicorn worker-count resolution (cost-optimization Opt 1).

The default must be 1 (single-garage: one OCR model instance), env-overridable,
and robust against bad values so a typo can never spawn a model-per-worker fleet
or take the API down.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

# gunicorn.conf.py lives at the backend root, not inside the app package.
_CONF_PATH = Path(__file__).resolve().parent.parent / "gunicorn.conf.py"


def _load_resolver():
    spec = importlib.util.spec_from_file_location("gunicorn_conf_under_test", _CONF_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module._resolve_workers


@pytest.fixture
def resolve(monkeypatch):
    monkeypatch.delenv("GUNICORN_WORKERS", raising=False)
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
    return _load_resolver(), monkeypatch


def test_defaults_to_one_worker(resolve):
    resolver, _ = resolve
    assert resolver() == 1


def test_gunicorn_workers_env_overrides(resolve):
    resolver, mp = resolve
    mp.setenv("GUNICORN_WORKERS", "4")
    assert resolver() == 4


def test_web_concurrency_used_when_gunicorn_workers_absent(resolve):
    resolver, mp = resolve
    mp.setenv("WEB_CONCURRENCY", "3")
    assert resolver() == 3


def test_gunicorn_workers_takes_precedence_over_web_concurrency(resolve):
    resolver, mp = resolve
    mp.setenv("WEB_CONCURRENCY", "3")
    mp.setenv("GUNICORN_WORKERS", "2")
    assert resolver() == 2


@pytest.mark.parametrize("bad", ["0", "-1", "abc", ""])
def test_invalid_values_fall_back_to_one(resolve, bad):
    resolver, mp = resolve
    mp.setenv("GUNICORN_WORKERS", bad)
    assert resolver() == 1


def test_conf_module_exposes_gunicorn_settings():
    """The module must define the settings gunicorn reads at boot."""
    os.environ.pop("GUNICORN_WORKERS", None)
    os.environ.pop("WEB_CONCURRENCY", None)
    spec = importlib.util.spec_from_file_location("gunicorn_conf_settings", _CONF_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.workers == 1
    assert module.worker_class == "uvicorn.workers.UvicornWorker"
    assert module.timeout >= 60  # OCR background tasks need headroom
    assert module.bind.endswith(":8000")
