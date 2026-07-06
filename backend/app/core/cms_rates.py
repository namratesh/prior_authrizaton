"""
Real CMS Physician Fee Schedule rate lookup: zip -> locality -> GPCI, joined
against RVUs, run through the standard Medicare payment formula.

// DEMO-REAL

    rate = (work_rvu * work_gpci + pe_rvu * pe_gpci + mp_rvu * mp_gpci) * CF

All inputs (RVUs, GPCIs, locality/county crosswalk, conversion factor) are
ingested from real CMS files in backend/data/rates/ by app/core/cms_ingest.py
into Postgres. This module only reads that data and caches results in Redis;
it does no ingestion itself.

Results are cached in Redis under `cms_rate:{cpt}:{zip_code}`.
"""
import os

import redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.cms_ingest import CMS_CONVERSION_FACTOR_2026

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def get_redis_client() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def _compute_rate(cpt: str, zip_code: str, db: Session) -> float | None:
    row = db.execute(
        text("SELECT state, locality_number FROM zip_locality WHERE zip_code = :zip"),
        {"zip": zip_code},
    ).first()
    if row is None:
        return None
    state, locality_number = row

    gpci_row = db.execute(
        text(
            "SELECT work_gpci, pe_gpci, mp_gpci FROM gpci_values "
            "WHERE state = :state AND locality_number = :locality"
        ),
        {"state": state, "locality": locality_number},
    ).first()
    if gpci_row is None:
        return None
    work_gpci, pe_gpci, mp_gpci = gpci_row

    rvu_row = db.execute(
        text(
            "SELECT work_rvu, pe_rvu_nonfacility, mp_rvu FROM rvu_values WHERE cpt = :cpt"
        ),
        {"cpt": cpt},
    ).first()
    if rvu_row is None:
        return None
    work_rvu, pe_rvu, mp_rvu = rvu_row

    return (
        work_rvu * work_gpci + pe_rvu * pe_gpci + mp_rvu * mp_gpci
    ) * CMS_CONVERSION_FACTOR_2026


def get_cms_rate(
    cpt: str,
    zip_code: str,
    db: Session,
    client: redis.Redis | None = None,
) -> float | None:
    """Geo-adjusted CMS benchmark rate for a CPT code billed from a zip code.

    Returns None if the CPT isn't RVU-payable (e.g. a drug/DME HCPCS code
    outside the Physician Fee Schedule) or the zip doesn't resolve to a known
    locality — callers should treat None as "rate unavailable, manual review
    required," never as zero.
    """
    r = client or get_redis_client()
    cache_key = f"cms_rate:{cpt}:{zip_code}"
    cached = r.get(cache_key)
    if cached is not None:
        return float(cached)

    rate = _compute_rate(cpt, zip_code, db)
    if rate is not None:
        r.set(cache_key, rate)
    return rate
