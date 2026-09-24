"""Query router: analytical (SQL RAG) vs knowledge (hybrid RAG), plus target collections.

Primary: an LLM classifier returning JSON. Fallback (no LLM configured / invalid output): a
transparent heuristic. The router only drives *routing and UX messages*; it is not a security
control - document access is enforced by the Qdrant filter and SQL access by ``can_use_sql``.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Literal

from app.llm.client import LLMClient, LLMError, LLMNotConfiguredError, get_llm
from app.llm.prompts import ROUTER_SYSTEM_PROMPT
from app.rbac import ALL_COLLECTIONS, Collection

logger = logging.getLogger(__name__)

Route = Literal["sql", "documents"]


@dataclass
class RouteDecision:
    route: Route
    collections: list[Collection] = field(default_factory=list)
    reason: str = ""
    method: Literal["llm", "heuristic"] = "heuristic"


# --- heuristic fallback -------------------------------------------------------------------

_AGGREGATE_RE = re.compile(
    r"\b(how many|number of|count|total|sum|average|avg|mean|median|most|least|highest|lowest|"
    r"top \d+|per (month|department|insurer|campus|category)|breakdown|trend|percentage|"
    r"proportion|ratio|statistics|stats|list (all|the)|which (department|insurer|equipment|"
    r"category|campus))\b",
    re.IGNORECASE,
)
_DATA_ENTITY_RE = re.compile(
    r"\b(claims?|tickets?|maintenance tickets?|approved amount|claimed amount|insurers?|"
    r"escalat\w*|rejected|pending|resolved|open tickets?)\b",
    re.IGNORECASE,
)

COLLECTION_KEYWORDS: dict[Collection, tuple[str, ...]] = {
    Collection.BILLING: (
        "billing",
        "insurance",
        "insurer",
        "claim",
        "pre-auth",
        "preauth",
        "pre-authorisation",
        "pre-authorization",
        "reimbursement",
        "cashless",
        "tpa",
        "icd",
        "procedure code",
        "co-pay",
        "copay",
        "sub-limit",
        "room rent",
        "rejection",
        "billing code",
        "exclusion",
    ),
    Collection.CLINICAL: (
        "drug",
        "formulary",
        "dose",
        "dosing",
        "dosage",
        "mg",
        "treatment protocol",
        "protocol",
        "diagnos",
        "reference range",
        "haemoglobin",
        "hemoglobin",
        "ecg",
        "abg",
        "blood gas",
        "diabetes",
        "hypertension",
        "pneumonia",
        "nstemi",
        "myocardial",
        "dengue",
        "copd",
        "antibiotic",
        "antimicrobial",
        "tumour marker",
        "clinical",
        "prescrib",
        "medication",
    ),
    Collection.NURSING: (
        "nursing",
        "nurse",
        "icu",
        "cannula",
        "catheter",
        "cvc",
        "ventilator",
        "nasogastric",
        "ngt",
        "restraint",
        "suction",
        "pressure injury",
        "bedsore",
        "infection control",
        "hand hygiene",
        "ppe",
        "isolation",
        "needlestick",
        "sharps",
        "waste segregation",
    ),
    Collection.EQUIPMENT: (
        "equipment",
        "device",
        "calibrat",
        "maintenance",
        "fault code",
        "monitor",
        "bm-500",
        "infusion pump",
        "ip-200",
        "driveflow",
        "autoclave",
        "steriliser",
        "sterilizer",
        "sterilpro",
        "x-ray",
        "radipro",
        "mx-150",
        "technician",
        "service schedule",
    ),
    Collection.GENERAL: (
        "leave",
        "holiday",
        "salary",
        "payslip",
        "provident",
        "gratuity",
        "handbook",
        "code of conduct",
        "conduct",
        "dress code",
        "grievance",
        "probation",
        "notice period",
        "appraisal",
        "cafeteria",
        "parking",
        "wi-fi",
        "password",
        "hr",
        "attendance",
        "harassment",
    ),
}


def heuristic_route(question: str) -> RouteDecision:
    q = question.lower()
    is_sql = bool(_AGGREGATE_RE.search(q) and _DATA_ENTITY_RE.search(q))
    collections = [c for c in ALL_COLLECTIONS if any(k in q for k in COLLECTION_KEYWORDS[c])]
    return RouteDecision(
        route="sql" if is_sql else "documents",
        collections=[] if is_sql else collections,
        reason="keyword heuristic (LLM router unavailable)",
        method="heuristic",
    )


# --- LLM router -----------------------------------------------------------------------------

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_router_output(raw: str) -> RouteDecision:
    match = _JSON_RE.search(raw or "")
    if not match:
        raise ValueError(f"router returned no JSON: {raw[:200]!r}")
    data = json.loads(match.group(0))
    route = str(data.get("route", "")).strip().lower()
    if route not in ("sql", "documents"):
        raise ValueError(f"invalid route {route!r}")
    valid = {c.value for c in ALL_COLLECTIONS}
    collections = [
        Collection(c)
        for c in dict.fromkeys(str(x).lower() for x in data.get("collections") or [])
        if c in valid
    ]
    return RouteDecision(
        route="sql" if route == "sql" else "documents",
        collections=collections,
        reason=str(data.get("reason", ""))[:300],
        method="llm",
    )


def route_question(question: str, llm: LLMClient | None = None) -> RouteDecision:
    try:
        llm = llm or get_llm()
        raw = llm.complete(ROUTER_SYSTEM_PROMPT, f"Question: {question}", max_tokens=200)
        decision = parse_router_output(raw)
    except (LLMNotConfiguredError, LLMError, ValueError) as exc:
        logger.warning("LLM router unavailable (%s); using heuristic", exc)
        decision = heuristic_route(question)
    logger.info(
        "route q=%r -> %s %s (%s)",
        question[:80],
        decision.route,
        [c.value for c in decision.collections],
        decision.method,
    )
    return decision
