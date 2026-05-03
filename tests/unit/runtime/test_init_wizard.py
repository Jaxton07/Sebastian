from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sebastian.cli.init_wizard import run_headless_wizard
from sebastian.config import Settings


@pytest.mark.asyncio
async def test_run_headless_wizard_creates_owner_and_secret(tmp_path: Path) -> None:
    owner_store = MagicMock()
    owner_store.owner_exists = AsyncMock(return_value=False)
    owner_store.create_owner = AsyncMock()

    secret_key_path = tmp_path / "secret.key"

    await run_headless_wizard(
        owner_store=owner_store,
        secret_key_path=secret_key_path,
        answers={"name": "Eric", "password": "hunter42"},
    )

    owner_store.create_owner.assert_awaited_once()
    kwargs = owner_store.create_owner.call_args.kwargs
    assert kwargs["name"] == "Eric"
    assert kwargs["password_hash"].startswith("$pbkdf2-sha256$")
    assert secret_key_path.exists()


@pytest.mark.asyncio
async def test_run_headless_wizard_refuses_if_owner_exists(tmp_path: Path) -> None:
    owner_store = MagicMock()
    owner_store.owner_exists = AsyncMock(return_value=True)
    owner_store.create_owner = AsyncMock()

    secret_key_path = tmp_path / "secret.key"

    with pytest.raises(RuntimeError, match="already initialized"):
        await run_headless_wizard(
            owner_store=owner_store,
            secret_key_path=secret_key_path,
            answers={"name": "Eric", "password": "hunter42"},
        )

    owner_store.create_owner.assert_not_awaited()


@pytest.mark.asyncio
async def test_interactive_headless_cli_creates_data_layout_before_db_init(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "fresh-sebastian"
    settings = Settings(sebastian_data_dir=str(data_root))
    answers = iter(["Jaxton", "hunter42", "hunter42"])

    import sebastian.store.database as db_module
    from sebastian.cli.init_wizard import run_interactive_headless_cli

    db_module._engine = None
    db_module._session_factory = None

    def prompt(_label: str, *, hide_input: bool = False) -> str:
        return next(answers)

    try:
        with (
            patch("sebastian.config.settings", settings),
            patch("sebastian.store.migration.migrate_layout_v2"),
            patch("typer.prompt", side_effect=prompt),
        ):
            await run_interactive_headless_cli()
    finally:
        if db_module._engine is not None:
            await db_module._engine.dispose()
        db_module._engine = None
        db_module._session_factory = None

    assert (data_root / "data" / "sebastian.db").exists()
    assert (data_root / "data" / "secret.key").exists()
