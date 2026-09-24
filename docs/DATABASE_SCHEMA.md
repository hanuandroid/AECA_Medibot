# `mediassist.db` — Schema & Value Formats

Source: `mediassist_data/db/mediassist.db` (SQLite). Inspected directly with `sqlite_master`,
`PRAGMA table_info` and `SELECT DISTINCT` queries — nothing below is assumed.
The SQL RAG prompt is generated from the live database at runtime by
`backend/app/sql_rag/schema.py::describe_schema`, so it cannot drift from this document.

Only two tables exist: `claims` and `maintenance_tickets`. No views, triggers or foreign keys.

## `claims` — 85 rows

| Column | Type | Format / values |
|---|---|---|
| `claim_id` | TEXT PK | `CLM-2024-1000` … `CLM-2024-1084` |
| `patient_id` | TEXT | `PAT-NNNNN` |
| `patient_name` | TEXT | free text (78 distinct) |
| `department` | TEXT | `cardiology` (20), `emergency` (4), `general_medicine` (16), `gynaecology` (11), `nephrology` (9), `neurology` (6), `orthopaedics` (19) |
| `claim_type` | TEXT | `cashless` (60), `reimbursement` (25) |
| `diagnosis_code` | TEXT | ICD-10 code, 25 distinct (e.g. `I21.4`, `N17.9`, `A09`, `S72.0`) |
| `insurer` | TEXT | `Bajaj Allianz`, `Care Health`, `HDFC Ergo`, `ICICI Lombard`, `New India Assurance`, `Niva Bupa`, `Star Health`, `United India` |
| `claimed_amount` | REAL | INR, 4 000 – 228 900 |
| `approved_amount` | REAL | INR, 3 800 – 198 800; **NULL** unless approved |
| `status` | TEXT | `approved` (44), `escalated` (8), `pending` (17), `rejected` (12), `submitted` (4) |
| `submitted_date` | TEXT | ISO `YYYY-MM-DD`, 2024-01-03 … 2024-12-19 |
| `resolved_date` | TEXT | ISO `YYYY-MM-DD`, 2024-01-06 … 2024-12-28; NULL when unresolved |

## `maintenance_tickets` — 78 rows

| Column | Type | Format / values |
|---|---|---|
| `ticket_id` | TEXT PK | `TKT-2024-2000` … `TKT-2024-2077` |
| `equipment_name` | TEXT | `BM-500 Monitor` (25), `DriveFlow IP-200` (19), `ElectroCautery EC-90` (6), `HemaCount HC-20` (3), `RadiPro MX-150` (13), `SterilPro 3000` (12) |
| `equipment_id` | TEXT | asset tag `EQ-<CAMPUS>-NNNN` |
| `category` | TEXT | `infusion` (19), `laboratory` (3), `monitoring` (25), `radiology` (13), `sterilisation` (12), `surgical` (6) |
| `campus` | TEXT | `MediAssist Bengaluru Onco Centre`, `MediAssist Hyderabad Central`, `MediAssist Mysuru Clinic Hub`, `MediAssist Pune Speciality`, `MediAssist Secunderabad` |
| `issue_type` | TEXT | `battery_replacement` (11), `calibration_due` (13), `fault_reported` (14), `preventive_maintenance` (18), `sensor_failure` (22) |
| `fault_code` | TEXT | `E-01`…`E-12`, `F-01`…`F-12`, `L-03`, `L-06`, `S-02`, `S-05`; NULL (30) for preventive work |
| `raised_by` | TEXT | staff name |
| `raised_date` | TEXT | ISO `YYYY-MM-DD`, 2024-01-08 … 2024-12-28 |
| `resolved_date` | TEXT | ISO `YYYY-MM-DD`; NULL when unresolved |
| `status` | TEXT | `escalated` (10), `in_progress` (15), `open` (11), `resolved` (42) |
| `resolution_note` | TEXT | fixed phrases, NULL when unresolved |

## Notes that shape the SQL RAG design

- **All data is from 2024.** Relative expressions ("last month", "this month") are resolved against
  `SQL_AS_OF_DATE`, defaulting to the latest date in the database (**2024-12-28**), so
  "last month" = November 2024. With the real current date every relative query would return 0,
  which would be correct but useless for a demo. The as-of date is stated in the prompt and is
  configurable.
- Categorical values are lower-case snake case (`in_progress`, `calibration_due`); the prompt lists
  the exact values so the LLM does not invent `'Open'` or `'In Progress'`.
- `approved_amount` is NULL for non-approved claims, so averages should filter on `status`.
- "Open tickets" is ambiguous (`open` only vs. everything not `resolved`); the prompt defines
  `status = 'open'` as the default and "unresolved" as `status != 'resolved'`.
