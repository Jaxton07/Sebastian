from __future__ import annotations

import pytest


def test_encrypt_decrypt_roundtrip(monkeypatch) -> None:
    monkeypatch.setattr("sebastian.config.settings.sebastian_jwt_secret", "test-secret-abc")
    from sebastian.llm.crypto import decrypt, encrypt

    plain = "sk-ant-api03-test-key"
    assert decrypt(encrypt(plain)) == plain


def test_different_plaintexts_produce_different_ciphertext(monkeypatch) -> None:
    monkeypatch.setattr("sebastian.config.settings.sebastian_jwt_secret", "test-secret-abc")
    from sebastian.llm.crypto import encrypt

    assert encrypt("key-a") != encrypt("key-b")


def test_ciphertext_is_not_plaintext(monkeypatch) -> None:
    monkeypatch.setattr("sebastian.config.settings.sebastian_jwt_secret", "test-secret-abc")
    from sebastian.llm.crypto import encrypt

    plain = "sk-ant-secret"
    assert plain not in encrypt(plain)
