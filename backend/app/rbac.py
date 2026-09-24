"""Role-based access control: the single source of truth for who may read what.

The access matrix is used in two places:

* at ingestion time, to stamp every chunk with ``access_roles`` (who may read it), and
* at query time, to build the Qdrant payload filter that is attached to *every* retrieval
  query. Restricted chunks are therefore never returned by Qdrant to the application.
"""

from __future__ import annotations

from enum import StrEnum

from qdrant_client import models


class Role(StrEnum):
    DOCTOR = "doctor"
    NURSE = "nurse"
    BILLING_EXECUTIVE = "billing_executive"
    TECHNICIAN = "technician"
    ADMIN = "admin"


class Collection(StrEnum):
    GENERAL = "general"
    CLINICAL = "clinical"
    NURSING = "nursing"
    BILLING = "billing"
    EQUIPMENT = "equipment"


ALL_COLLECTIONS: tuple[Collection, ...] = (
    Collection.GENERAL,
    Collection.CLINICAL,
    Collection.NURSING,
    Collection.BILLING,
    Collection.EQUIPMENT,
)

ROLE_COLLECTIONS: dict[Role, frozenset[Collection]] = {
    Role.DOCTOR: frozenset({Collection.CLINICAL, Collection.NURSING, Collection.GENERAL}),
    Role.NURSE: frozenset({Collection.NURSING, Collection.GENERAL}),
    Role.BILLING_EXECUTIVE: frozenset({Collection.BILLING, Collection.GENERAL}),
    Role.TECHNICIAN: frozenset({Collection.EQUIPMENT, Collection.GENERAL}),
    Role.ADMIN: frozenset(ALL_COLLECTIONS),
}

SQL_ROLES: frozenset[Role] = frozenset({Role.BILLING_EXECUTIVE, Role.ADMIN})

COLLECTION_LABELS: dict[Collection, str] = {
    Collection.GENERAL: "General (HR handbook, leave policy, code of conduct, FAQs)",
    Collection.CLINICAL: "Clinical (treatment protocols, drug formulary, diagnostics)",
    Collection.NURSING: "Nursing (ICU procedures, infection control)",
    Collection.BILLING: "Billing (insurance billing codes, claim procedures)",
    Collection.EQUIPMENT: "Equipment (operation & maintenance manuals)",
}

ROLE_LABELS: dict[Role, str] = {
    Role.DOCTOR: "Doctor",
    Role.NURSE: "Nurse",
    Role.BILLING_EXECUTIVE: "Billing Executive",
    Role.TECHNICIAN: "Technician",
    Role.ADMIN: "Admin",
}


class UnknownRoleError(ValueError):
    pass


def parse_role(value: str) -> Role:
    """Strictly parse a role name. Unknown roles are rejected, never defaulted."""
    try:
        return Role(value)
    except ValueError as exc:
        raise UnknownRoleError(f"Unknown role: {value!r}") from exc


def parse_collection(value: str) -> Collection:
    return Collection(value)


def allowed_collections(role: Role) -> list[Collection]:
    """Collections the role may read, in a stable display order."""
    allowed = ROLE_COLLECTIONS[role]
    return [c for c in ALL_COLLECTIONS if c in allowed]


def restricted_collections(role: Role) -> list[Collection]:
    allowed = ROLE_COLLECTIONS[role]
    return [c for c in ALL_COLLECTIONS if c not in allowed]


def roles_for_collection(collection: Collection) -> list[str]:
    """Roles permitted to read chunks of ``collection`` (stamped on each chunk at ingestion)."""
    return [r.value for r in Role if collection in ROLE_COLLECTIONS[r]]


def can_use_sql(role: Role) -> bool:
    return role in SQL_ROLES


def build_access_filter(role: Role) -> models.Filter:
    """Qdrant payload filter restricting results to chunks readable by ``role``.

    ``access_roles`` is a keyword array on each point; ``MatchValue`` on an array field
    matches when any element equals the value. We additionally pin ``collection`` to the
    role's allowed collections so that a mis-stamped chunk still cannot leak across
    collections (defence in depth - both conditions must hold).
    """
    role = parse_role(role.value if isinstance(role, Role) else str(role))
    return models.Filter(
        must=[
            models.FieldCondition(key="access_roles", match=models.MatchValue(value=role.value)),
            models.FieldCondition(
                key="collection",
                match=models.MatchAny(any=[c.value for c in allowed_collections(role)]),
            ),
        ]
    )


def describe_access(role: Role) -> str:
    names = [c.value for c in allowed_collections(role)]
    if len(names) == 1:
        return f"the {names[0]} collection"
    return "the " + ", ".join(names[:-1]) + f" and {names[-1]} collections"
