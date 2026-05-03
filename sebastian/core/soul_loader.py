from __future__ import annotations

from hashlib import sha256
from pathlib import Path


class SoulLoader:
    def __init__(
        self,
        souls_dir: Path,
        builtin_souls: dict[str, str],
        upgradable_builtin_souls: dict[str, tuple[str, ...]] | None = None,
        upgradable_builtin_soul_hashes: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        self._souls_dir = souls_dir
        self._builtin_souls = builtin_souls
        self._upgradable_builtin_souls = upgradable_builtin_souls or {}
        self._upgradable_builtin_soul_hashes = upgradable_builtin_soul_hashes or {}
        self.current_soul: str = "sebastian"

    def list_souls(self) -> list[str]:
        if not self._souls_dir.exists():
            return []
        return sorted(p.stem for p in self._souls_dir.glob("*.md") if not p.stem.startswith("."))

    def load(self, soul_name: str) -> str | None:
        # reject empty, path separators, traversal, hidden files
        if not soul_name or soul_name != Path(soul_name).name or soul_name.startswith("."):
            return None
        path = self._souls_dir / f"{soul_name}.md"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def ensure_defaults(self) -> None:
        self._souls_dir.mkdir(parents=True, exist_ok=True)
        for name, content in self._builtin_souls.items():
            path = self._souls_dir / f"{name}.md"
            if not path.exists():
                path.write_text(content, encoding="utf-8")
                continue
            existing = path.read_text(encoding="utf-8")
            legacy_contents = self._upgradable_builtin_souls.get(name, ())
            legacy_hashes = self._upgradable_builtin_soul_hashes.get(name, ())
            existing_hash = sha256(existing.encode("utf-8")).hexdigest()
            if existing in legacy_contents or existing_hash in legacy_hashes:
                path.write_text(content, encoding="utf-8")
