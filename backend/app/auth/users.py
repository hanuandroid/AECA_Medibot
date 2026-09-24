"""Demo user store (development only).

Usernames/roles are the five demo identities from the assignment. Passwords are never
hard-coded: they come from ``DEMO_USERS`` ("user:role:password;...") or, if that is empty,
from a shared ``DEMO_PASSWORD``. Passwords are kept only as salted PBKDF2 hashes in memory.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from functools import lru_cache

from app.config import get_settings
from app.rbac import Role, parse_role

logger = logging.getLogger(__name__)

DEFAULT_DEMO_ACCOUNTS: dict[str, tuple[Role, str]] = {
    "dr.mehta": (Role.DOCTOR, "Dr. Mehta"),
    "nurse.priya": (Role.NURSE, "Nurse Priya"),
    "billing.ravi": (Role.BILLING_EXECUTIVE, "Ravi (Billing)"),
    "tech.anand": (Role.TECHNICIAN, "Anand (Biomedical)"),
    "admin.sys": (Role.ADMIN, "System Admin"),
}

_ITERATIONS = 200_000


@dataclass(frozen=True)
class User:
    username: str
    role: Role
    display_name: str
    salt: bytes
    password_hash: bytes

    def check_password(self, password: str) -> bool:
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), self.salt, _ITERATIONS)
        return hmac.compare_digest(candidate, self.password_hash)


class UsersNotConfiguredError(RuntimeError):
    pass


def _make_user(username: str, role: Role, display: str, password: str) -> User:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return User(username, role, display, salt, digest)


@lru_cache(maxsize=1)
def load_users() -> dict[str, User]:
    s = get_settings()
    users: dict[str, User] = {}
    if s.demo_users.strip():
        for entry in s.demo_users.split(";"):
            if not entry.strip():
                continue
            try:
                username, role, password = entry.strip().split(":", 2)
            except ValueError as exc:
                raise UsersNotConfiguredError(
                    "DEMO_USERS entries must look like username:role:password"
                ) from exc
            parsed = parse_role(role.strip())
            display = DEFAULT_DEMO_ACCOUNTS.get(username.strip(), (parsed, username))[1]
            users[username.strip()] = _make_user(username.strip(), parsed, display, password)
    elif s.demo_password:
        for username, (role, display) in DEFAULT_DEMO_ACCOUNTS.items():
            users[username] = _make_user(username, role, display, s.demo_password)
    if not users:
        raise UsersNotConfiguredError(
            "No demo users configured: set DEMO_PASSWORD or DEMO_USERS in backend/.env"
        )
    return users


def authenticate(username: str, password: str) -> User | None:
    users = load_users()
    user = users.get(username.strip().lower())
    if user is None:
        # Constant-ish time: still run a hash so unknown users are not trivially enumerable.
        _make_user("x", Role.NURSE, "x", password)
        return None
    return user if user.check_password(password) else None
