"""RBAC matrix, collection access and Qdrant filter generation (unit level)."""

from __future__ import annotations

import pytest
from qdrant_client import models

from app.rbac import (
    ALL_COLLECTIONS,
    Collection,
    Role,
    UnknownRoleError,
    allowed_collections,
    build_access_filter,
    can_use_sql,
    parse_role,
    restricted_collections,
    roles_for_collection,
)

EXPECTED = {
    Role.DOCTOR: {"clinical", "nursing", "general"},
    Role.NURSE: {"nursing", "general"},
    Role.BILLING_EXECUTIVE: {"billing", "general"},
    Role.TECHNICIAN: {"equipment", "general"},
    Role.ADMIN: {"clinical", "nursing", "billing", "equipment", "general"},
}


@pytest.mark.parametrize("role", list(Role))
def test_access_matrix_matches_assignment(role: Role) -> None:
    assert {c.value for c in allowed_collections(role)} == EXPECTED[role]
    assert {c.value for c in restricted_collections(role)} == (
        {c.value for c in ALL_COLLECTIONS} - EXPECTED[role]
    )


def test_roles_for_collection_is_inverse_of_matrix() -> None:
    assert sorted(roles_for_collection(Collection.GENERAL)) == sorted(r.value for r in Role)
    assert sorted(roles_for_collection(Collection.CLINICAL)) == ["admin", "doctor"]
    assert sorted(roles_for_collection(Collection.NURSING)) == ["admin", "doctor", "nurse"]
    assert sorted(roles_for_collection(Collection.BILLING)) == ["admin", "billing_executive"]
    assert sorted(roles_for_collection(Collection.EQUIPMENT)) == ["admin", "technician"]


def test_sql_access_only_billing_and_admin() -> None:
    assert {r for r in Role if can_use_sql(r)} == {Role.BILLING_EXECUTIVE, Role.ADMIN}


@pytest.mark.parametrize("bad", ["", "Admin", "root", "doctor ", "admin'--", "billing"])
def test_unknown_roles_are_rejected(bad: str) -> None:
    with pytest.raises(UnknownRoleError):
        parse_role(bad)


@pytest.mark.parametrize("role", list(Role))
def test_access_filter_structure(role: Role) -> None:
    flt = build_access_filter(role)
    assert isinstance(flt, models.Filter)
    assert flt.should is None and flt.must_not is None  # nothing that could widen access
    conditions = {c.key: c for c in flt.must}  # type: ignore[union-attr]
    roles_cond = conditions["access_roles"]
    assert isinstance(roles_cond.match, models.MatchValue)
    assert roles_cond.match.value == role.value
    coll_cond = conditions["collection"]
    assert isinstance(coll_cond.match, models.MatchAny)
    assert set(coll_cond.match.any) == EXPECTED[role]


def test_access_filter_rejects_non_role() -> None:
    with pytest.raises(UnknownRoleError):
        build_access_filter("superuser")  # type: ignore[arg-type]
