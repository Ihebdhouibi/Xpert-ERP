"""One-time script: add get_logger to all router files."""
import re
from pathlib import Path

modules_dir = Path("backend/app/modules")
router_files = list(modules_dir.rglob("router.py"))
router_files += list(modules_dir.rglob("stock_router.py"))
router_files += list(modules_dir.rglob("time_entry_router.py"))


def component_name(fpath: Path) -> str:
    parts = list(fpath.parts)
    idx = parts.index("modules")
    module = parts[idx + 1]
    stem = fpath.stem
    if stem == "router":
        return f"{module}.router"
    return f"{module}.{stem}"


for fpath in sorted(router_files):
    text = fpath.read_text(encoding="utf-8")
    comp = component_name(fpath)

    if "from app.core.logging import get_logger" in text and "logger = get_logger" in text:
        print(f"SKIP: {fpath}")
        continue

    if "from app.core.logging import get_logger" not in text:
        lines = text.splitlines(keepends=True)
        last_import_idx = -1
        for i, line in enumerate(lines):
            if line.startswith("from ") or line.startswith("import "):
                last_import_idx = i
        if last_import_idx >= 0:
            lines.insert(last_import_idx + 1, "from app.core.logging import get_logger\n")
            text = "".join(lines)

    if "logger = get_logger" not in text:
        new_text = re.sub(
            r"(router = APIRouter\([^)]*\))",
            lambda m: m.group(0) + f'\nlogger = get_logger("{comp}")',
            text,
            count=1,
        )
        if new_text == text:
            print(f"WARN could not insert logger: {fpath}")
        else:
            text = new_text

    fpath.write_text(text, encoding="utf-8")
    print(f"OK: {fpath}")
