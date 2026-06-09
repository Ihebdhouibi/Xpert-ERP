"""Guard test: every permission code enforced by a router must exist in the
canonical catalog (app.modules.rbac.permissions).

This is the regression test for the bug class that left the cash-session,
supplier, inspection, config and sequence endpoints returning 403 for every
role: a router guarded an endpoint with a permission code that no role held
because the code was never defined in / granted by the seed. Keeping router
codes a subset of the catalog makes that drift a test failure instead of a
silent production 403.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.modules.rbac.permissions import ALL_PERMISSION_CODES, PERMISSIONS

# Directory holding every feature module (…/backend/app/modules).
_MODULES_DIR = Path(__file__).resolve().parents[1] / "app" / "modules"

# The RBAC machinery lives under app/modules/rbac (require_permission is defined
# there and the catalog docstring shows illustrative calls). Real endpoint
# guards live in feature routers, never in rbac/, so skip that directory.
_EXCLUDED_DIR = _MODULES_DIR / "rbac"

_REQUIRE_PERMISSION_RE = re.compile(r"""require_permission\(\s*["']([^"']+)["']""")


def _iter_required_codes() -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for path in _MODULES_DIR.rglob("*.py"):
        if _EXCLUDED_DIR in path.parents:
            continue
        text = path.read_text(encoding="utf-8")
        for code in _REQUIRE_PERMISSION_RE.findall(text):
            found.append((path, code))
    return found


def test_every_router_permission_code_is_in_the_catalog() -> None:
    unknown = sorted(
        {
            f"{code}  (in {path.relative_to(_MODULES_DIR)})"
            for path, code in _iter_required_codes()
            if code not in ALL_PERMISSION_CODES
        }
    )
    assert not unknown, (
        "These require_permission() codes are not in the canonical catalog "
        "(app/modules/rbac/permissions.py); no role can ever hold them, so the "
        "endpoint returns 403 for everyone:\n  " + "\n  ".join(unknown)
    )


def test_catalog_has_no_duplicate_codes() -> None:
    codes = [p["code"] for p in PERMISSIONS]
    duplicates = sorted({c for c in codes if codes.count(c) > 1})
    assert not duplicates, f"Duplicate permission codes in catalog: {duplicates}"


def test_at_least_one_code_is_scanned() -> None:
    # Guards against the regex / path silently matching nothing and the
    # subset assertion passing vacuously.
    assert _iter_required_codes(), "No require_permission() calls were found to check."
