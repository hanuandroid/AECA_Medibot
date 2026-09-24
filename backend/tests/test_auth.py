from __future__ import annotations

import time

import jwt
import pytest

from app.auth import tokens
from app.auth.tokens import AuthError, create_access_token, decode_token
from app.auth.users import DEFAULT_DEMO_ACCOUNTS, authenticate, load_users
from app.config import get_settings
from app.rbac import Role

PASSWORD = get_settings().demo_password


def test_five_demo_users_one_per_role() -> None:
    users = load_users()
    assert set(users) == {"dr.mehta", "nurse.priya", "billing.ravi", "tech.anand", "admin.sys"}
    assert {u.role for u in users.values()} == set(Role)
    for name, (role, _) in DEFAULT_DEMO_ACCOUNTS.items():
        assert users[name].role == role


def test_passwords_are_not_stored_in_plain_text() -> None:
    user = load_users()["dr.mehta"]
    assert PASSWORD.encode() not in user.password_hash
    assert not hasattr(user, "password")


@pytest.mark.parametrize(
    ("username", "role"),
    [
        ("dr.mehta", Role.DOCTOR),
        ("nurse.priya", Role.NURSE),
        ("billing.ravi", Role.BILLING_EXECUTIVE),
        ("tech.anand", Role.TECHNICIAN),
        ("admin.sys", Role.ADMIN),
    ],
)
def test_authenticate_success(username: str, role: Role) -> None:
    user = authenticate(username, PASSWORD)
    assert user is not None and user.role == role


def test_authenticate_rejects_wrong_password_and_unknown_user() -> None:
    assert authenticate("dr.mehta", PASSWORD + "x") is None
    assert authenticate("mallory", PASSWORD) is None
    assert authenticate("dr.mehta", "") is None


def test_token_round_trip_carries_role() -> None:
    token, _ = create_access_token("nurse.priya", Role.NURSE, "Nurse Priya")
    data = decode_token(token)
    assert data.username == "nurse.priya"
    assert data.role is Role.NURSE


def test_tampered_token_role_is_rejected() -> None:
    token, _ = create_access_token("nurse.priya", Role.NURSE)
    claims = jwt.decode(token, options={"verify_signature": False})
    claims["role"] = "admin"
    forged = jwt.encode(claims, "attacker-secret-" + "y" * 40, algorithm="HS256")
    with pytest.raises(AuthError):
        decode_token(forged)


def test_alg_none_token_is_rejected() -> None:
    token, _ = create_access_token("nurse.priya", Role.NURSE)
    claims = jwt.decode(token, options={"verify_signature": False})
    claims["role"] = "admin"
    unsigned = jwt.encode(claims, key="", algorithm="none")
    with pytest.raises(AuthError):
        decode_token(unsigned)


def test_unknown_role_in_validly_signed_token_is_rejected() -> None:
    claims = {"sub": "x", "role": "superuser", "iss": tokens.ISSUER, "exp": int(time.time()) + 60}
    token = jwt.encode(claims, tokens._secret(), algorithm="HS256")
    with pytest.raises(AuthError):
        decode_token(token)


def test_expired_token_is_rejected() -> None:
    claims = {"sub": "x", "role": "admin", "iss": tokens.ISSUER, "exp": int(time.time()) - 10}
    token = jwt.encode(claims, tokens._secret(), algorithm="HS256")
    with pytest.raises(AuthError, match="expired"):
        decode_token(token)
