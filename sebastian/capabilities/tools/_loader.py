from __future__ import annotations

import importlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_tools() -> None:
    """Scan capabilities/tools/ and import:
    1. Flat .py modules (non-underscore-prefixed)
    2. Subdirectory packages containing __init__.py (non-underscore-prefixed)

    Each module's @tool decorators self-register into core.tool._tools.
    """
    tools_dir = Path(__file__).parent

    # 1. Flat .py files
    for path in sorted(tools_dir.glob("*.py")):
        if path.stem.startswith("_"):
            continue
        module_name = f"sebastian.capabilities.tools.{path.stem}"
        try:
            importlib.import_module(module_name)
            logger.info("Loaded tool module: %s", path.stem)
        except Exception:
            logger.exception("Failed to load tool module: %s", path.stem)

    # 2. Subdirectory packages
    for entry in sorted(tools_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        if not (entry / "__init__.py").exists():
            continue
        module_name = f"sebastian.capabilities.tools.{entry.name}"
        try:
            importlib.import_module(module_name)
            logger.info("Loaded tool package: %s", entry.name)
        except Exception:
            logger.exception("Failed to load tool package: %s", entry.name)
