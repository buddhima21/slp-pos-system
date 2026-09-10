"""Password hashing behaviour (SRS Section 4 — Security)."""

from __future__ import annotations

import pytest

from slp_pos.services.auth_service import hash_password, verify_password


def test_hash_is_not_plaintext():
    h = hash_password("s3cret")
    assert "s3cret" not in h
    assert h.startswith("pbkdf2_sha256$")


def test_verify_accepts_correct_password():
    h = hash_password("correct horse")
    assert verify_password("correct horse", h) is True


def test_verify_rejects_wrong_password():
    h = hash_password("correct horse")
    assert verify_password("wrong horse", h) is False


def test_two_hashes_of_same_password_differ():
    assert hash_password("same") != hash_password("same")  # random salt


def test_empty_password_rejected():
    with pytest.raises(ValueError):
        hash_password("")


def test_verify_handles_garbage_input():
    assert verify_password("x", "not-a-valid-hash") is False
