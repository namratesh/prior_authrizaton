"""
Ingests real 2026 CMS Physician Fee Schedule data from local files in
backend/data/rates/ into Postgres. No network calls — every file here was
already on disk before this module was written.

// MVP-REAL

Sources (all backend/data/rates/, verbatim CMS 2026 January release):
  - PPRRVU2026_Jan_nonQPP.csv  -> rvu_values      (Work/PE/MP RVUs per CPT/HCPCS)
  - GPCI2026.csv               -> gpci_values     (geographic cost indices per locality)
  - 26LOCCO.csv                -> locality_counties (county -> locality crosswalk)

The one non-CMS input is backend/app/data/zip_county_subset.csv: a 5-row
zip->county mapping using general public geography (not CMS data), scoped
only to the 5 Hero Cases, needed because CMS's own zip->locality crosswalk
isn't among the local files. Everything downstream of that single join
(locality lookup, GPCI, RVUs, conversion factor, the final rate) is real CMS
data and real math.

CMS_CONVERSION_FACTOR_2026 is not a supplied constant — it's read directly
off the RVU file, which stamps the same value ("CONV FACTOR" column) on
every non-anesthesia row: 33.4009.
"""
import csv
import re
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

RATES_DIR = Path(__file__).parent.parent.parent / "data" / "rates"
ZIP_COUNTY_SUBSET_PATH = Path(__file__).parent.parent / "data" / "zip_county_subset.csv"

RVU_CSV = RATES_DIR / "PPRRVU2026_Jan_nonQPP.csv"
GPCI_CSV = RATES_DIR / "GPCI2026.csv"
LOCCO_CSV = RATES_DIR / "26LOCCO.csv"

CMS_CONVERSION_FACTOR_2026 = 33.4009

# Physician Fee Schedule status codes that are actually paid via the RVU
# formula. Everything else (e.g. "E" = paid under a different CMS system,
# drugs/DME) has RVUs of 0.00 in this file and must not be treated as a real
# rate.
RVU_PAYABLE_STATUS_CODES = {"A", "R", "T"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().upper()


def _strip_county_suffix(s: str) -> str:
    s = _norm(s)
    s = re.sub(r"\b(COUNTY|CNTY|CO\.?)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_rvu(path: Path = RVU_CSV) -> dict[str, dict]:
    """CPT/HCPCS -> {description, status_code, work_rvu, pe_rvu_nonfacility, mp_rvu}.

    Only keeps codes with a real, non-zero RVU-payable status. Column
    indices below were confirmed by inspecting the file's actual header rows
    (row 9, 0-indexed) before writing this parser — not assumed.
    """
    out: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    for r in rows[10:]:
        if len(r) < 11 or not r[0]:
            continue
        cpt, desc, status = r[0].strip(), r[2].strip(), r[3].strip()
        try:
            work_rvu = float(r[5])
            pe_rvu = float(r[6])
            mp_rvu = float(r[10])
        except ValueError:
            continue
        if status not in RVU_PAYABLE_STATUS_CODES:
            continue
        if work_rvu == 0 and pe_rvu == 0 and mp_rvu == 0:
            continue
        out[cpt] = {
            "description": desc,
            "status_code": status,
            "work_rvu": work_rvu,
            "pe_rvu_nonfacility": pe_rvu,
            "mp_rvu": mp_rvu,
        }
    return out


def parse_gpci(path: Path = GPCI_CSV) -> dict[tuple[str, str], dict]:
    """(state, locality_number) -> {locality_name, work_gpci, pe_gpci, mp_gpci}."""
    out: dict[tuple[str, str], dict] = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    for r in rows[3:]:
        if len(r) < 8 or not r[1] or not r[2]:
            continue
        state = r[1].strip().upper()
        locality = r[2].strip()
        try:
            work_gpci = float(r[5])  # "with 1.0 floor" column, per current CMS floor policy
            pe_gpci = float(r[6])
            mp_gpci = float(r[7])
        except ValueError:
            continue
        out[(state, locality)] = {
            "locality_name": r[3].strip(),
            "work_gpci": work_gpci,
            "pe_gpci": pe_gpci,
            "mp_gpci": mp_gpci,
        }
    return out


def parse_locco(path: Path = LOCCO_CSV) -> list[dict]:
    """Rows of {mac, state, locality_number, fee_schedule_area, counties_raw}.

    26LOCCO.csv groups rows by state with blank-line separators; only the
    first row of a state's group carries the state name, so it's carried
    forward until the next blank-line-delimited group starts.
    """
    out: list[dict] = []
    current_state = None
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    for r in rows[3:]:
        cells = [c.strip() for c in r]
        if not any(cells) or cells[0].startswith("*"):
            current_state = None
            continue
        if len(cells) < 5 or not cells[0]:
            continue
        mac, locality, state, area, counties = cells[0], cells[1], cells[2], cells[3], cells[4]
        if state:
            current_state = state
        if not current_state:
            continue
        out.append(
            {
                "mac": mac,
                "state": current_state,
                "locality_number": locality,
                "fee_schedule_area": area,
                "counties_raw": counties,
            }
        )
    return out


# state name (as it appears in 26LOCCO.csv) -> 2-letter postal abbreviation,
# only for the states the Hero Cases actually need.
STATE_ABBREV = {
    "ALABAMA": "AL",
    "CALIFORNIA": "CA",
    "GEORGIA": "GA",
    "ILLINOIS": "IL",
    "NEW YORK": "NY",
}


def resolve_zip_localities(
    zip_county_path: Path = ZIP_COUNTY_SUBSET_PATH,
    locco_rows: list[dict] | None = None,
) -> tuple[list[dict], list[str]]:
    """Match each (zip, county, state) against locco_rows to find its locality.

    Returns (resolved, failures). `resolved` entries are
    {zip_code, county, state, locality_number}. Any zip that can't be
    matched is reported in `failures` rather than silently defaulted.
    """
    locco_rows = locco_rows if locco_rows is not None else parse_locco()
    resolved: list[dict] = []
    failures: list[str] = []

    with open(zip_county_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(row for row in f if not row.startswith("#"))
        zip_rows = list(reader)

    for row in zip_rows:
        zip_code, county, state = row["zip"].strip(), row["county"].strip(), row["state"].strip()
        county_norm = _strip_county_suffix(county)
        state_rows = [lr for lr in locco_rows if STATE_ABBREV.get(lr["state"], lr["state"]) == state]

        match = None
        # 1. Specific-county match: county name appears as a whole word/phrase
        # inside the free-text Counties field (excluding statewide catch-alls).
        for lr in state_rows:
            if lr["counties_raw"].strip().upper() in ("ALL COUNTIES",):
                continue
            counties_field_norm = _strip_county_suffix(lr["counties_raw"])
            if re.search(rf"\b{re.escape(county_norm)}\b", counties_field_norm):
                match = lr
                break
        # 2. Fall back to the state's STATEWIDE/ALL COUNTIES row.
        if match is None:
            for lr in state_rows:
                if lr["counties_raw"].strip().upper() == "ALL COUNTIES":
                    match = lr
                    break

        if match is None:
            failures.append(f"{zip_code} ({county}, {state}): no locality match found")
            print(f"FAILED to resolve locality for {zip_code} ({county}, {state})")
            continue

        print(
            f"Resolved {zip_code} ({county}, {state}) -> "
            f"locality {match['locality_number']} / {match['fee_schedule_area']} "
            f"(matched county field: {match['counties_raw']!r})"
        )
        resolved.append(
            {
                "zip_code": zip_code,
                "county": county,
                "state": state,
                "locality_number": match["locality_number"],
            }
        )

    return resolved, failures


def ingest_all(db: Session) -> None:
    """Populate rvu_values, gpci_values, locality_counties, zip_locality.

    Idempotent: clears and reloads each table so this can be safely rerun.
    """
    rvu = parse_rvu()
    gpci = parse_gpci()
    locco_rows = parse_locco()
    resolved, failures = resolve_zip_localities(locco_rows=locco_rows)
    if failures:
        raise ValueError(f"{len(failures)} zip(s) failed to resolve a locality: {failures}")

    db.execute(text("TRUNCATE TABLE rvu_values, gpci_values, locality_counties, zip_locality"))

    for cpt, v in rvu.items():
        db.execute(
            text(
                "INSERT INTO rvu_values (cpt, description, status_code, work_rvu, "
                "pe_rvu_nonfacility, mp_rvu) VALUES (:cpt, :description, :status_code, "
                ":work_rvu, :pe_rvu_nonfacility, :mp_rvu)"
            ),
            {"cpt": cpt, **v},
        )

    for (state, locality), v in gpci.items():
        db.execute(
            text(
                "INSERT INTO gpci_values (state, locality_number, locality_name, "
                "work_gpci, pe_gpci, mp_gpci) VALUES (:state, :locality_number, "
                ":locality_name, :work_gpci, :pe_gpci, :mp_gpci)"
            ),
            {"state": state, "locality_number": locality, **v},
        )

    for lr in locco_rows:
        db.execute(
            text(
                "INSERT INTO locality_counties (id, mac, state, locality_number, "
                "fee_schedule_area, counties_raw) VALUES (:id, :mac, "
                ":state, :locality_number, :fee_schedule_area, :counties_raw)"
            ),
            {**lr, "id": str(uuid.uuid4())},
        )

    for r in resolved:
        db.execute(
            text(
                "INSERT INTO zip_locality (zip_code, county, state, locality_number) "
                "VALUES (:zip_code, :county, :state, :locality_number)"
            ),
            r,
        )

    db.commit()
    print(
        f"Ingested {len(rvu)} RVU codes, {len(gpci)} GPCI localities, "
        f"{len(locco_rows)} locality/county rows, {len(resolved)} zip mappings."
    )


if __name__ == "__main__":
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        ingest_all(session)
    finally:
        session.close()
