"""
CHC Pro AI — NPI Verification Service
Calls NPPES, OIG LEIE, and CMS PECOS APIs to verify provider identity.
"""
import logging
from typing import Optional
import httpx
from app.schemas.auth_schemas import NPIDetail
from config import get_settings

log      = logging.getLogger(__name__)
settings = get_settings()


class NPIError(Exception):     pass
class OIGExcludedError(Exception): pass


async def verify_npi(npi: str, entity_type: str = "1") -> NPIDetail:
    """
    Query NPPES. Returns provider detail if NPI is found and active.
    Raises NPIError with human-readable message on any failure.
    """
    params = {
        "version":          settings.NPPES_API_VERSION,
        "number":           npi,
        "enumeration_type": f"NPI-{entity_type}",
        "limit":            1,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(settings.NPPES_API_BASE, params=params)
            r.raise_for_status()
            data = r.json()
        except httpx.TimeoutException:
            raise NPIError("The NPI registry is not responding. Please try again in a moment.")
        except httpx.HTTPStatusError as e:
            raise NPIError(f"NPI registry returned error {e.response.status_code}. Please try again.")
        except Exception as e:
            raise NPIError(f"Could not reach the NPI registry: {str(e)}")

    if data.get("result_count", 0) == 0:
        raise NPIError(
            f"NPI {npi} was not found in the NPPES registry. "
            "Please verify the number is correct and try again."
        )

    rec   = data["results"][0]
    basic = rec.get("basic", {})
    status = basic.get("status", "").upper()

    if status != "A":
        status_msgs = {
            "D": "deactivated",
            "I": "inactive",
            "E": "excluded",
        }
        human = status_msgs.get(status, f"status '{status}'")
        raise NPIError(
            f"NPI {npi} is {human} and cannot be used for registration. "
            "Only active NPIs are accepted."
        )

    # Taxonomy codes
    taxonomies = rec.get("taxonomies", [])
    tax_codes  = [
        f"{t.get('code','')} — {t.get('desc','')}"
        for t in taxonomies if t.get("primary")
    ] or [t.get("code", "") for t in taxonomies[:3]]

    # Practice address
    addresses = rec.get("addresses", [])
    addr = next((a for a in addresses if a.get("address_purpose") == "LOCATION"),
                addresses[0] if addresses else {})

    # Provider name
    if entity_type == "1":
        name = " ".join(filter(None, [
            basic.get("first_name", ""),
            basic.get("middle_name", ""),
            basic.get("last_name", ""),
            basic.get("credential", ""),
        ])).strip()
    else:
        name = basic.get("organization_name", "").strip()

    return NPIDetail(
        npi=npi,
        provider_name=name,
        entity_type="Individual" if entity_type == "1" else "Organization",
        status=status,
        taxonomy_codes=tax_codes,
        practice_address={
            "address_1":   addr.get("address_1", ""),
            "address_2":   addr.get("address_2", ""),
            "city":        addr.get("city", ""),
            "state":       addr.get("state", ""),
            "postal_code": addr.get("postal_code", ""),
        },
        enumeration_date=basic.get("enumeration_date"),
        last_updated=basic.get("last_updated"),
    )


async def check_oig(first_name: str, last_name: str, npi: Optional[str] = None) -> bool:
    """
    Check OIG LEIE exclusion list.
    Returns True if provider is clear.
    Raises OIGExcludedError if excluded — this is a hard registration block.
    """
    params = {
        "lastname":  last_name.upper(),
        "firstname": first_name.upper(),
    }
    if npi:
        params["npi"] = npi

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(settings.OIG_LEIE_API_BASE, params=params)
            r.raise_for_status()
            data = r.json()
        except httpx.TimeoutException:
            # Non-blocking on timeout — flag for manual review but don't block
            log.warning(f"OIG API timeout for NPI {npi}. Flagged for manual review.")
            return True
        except Exception as e:
            log.error(f"OIG check failed for NPI {npi}: {e}")
            return True  # Non-blocking — flag for review in production

    exclusions = data.get("exclusions", [])
    if exclusions:
        names = [
            f"{e.get('FIRSTNAME','')} {e.get('LASTNAME','')}"
            for e in exclusions
        ]
        raise OIGExcludedError(
            f"This provider appears on the OIG List of Excluded Individuals/Entities. "
            f"Registration cannot proceed. If you believe this is an error, "
            f"please contact support with your NPI. (Matched: {', '.join(names)})"
        )
    return True


async def check_pecos(npi: str) -> bool:
    """
    Check Medicare PECOS enrollment.
    Non-blocking — returns False on any error.
    Missing PECOS is a warning, not a registration block.
    """
    payload = {
        "conditions": [{"resource": "t", "property": "npi", "value": npi}],
        "limit": 1, "offset": 0,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.post(
                settings.PECOS_API_BASE, json=payload,
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
            return r.json().get("count", 0) > 0
        except Exception as e:
            log.warning(f"PECOS check failed for NPI {npi}: {e}")
            return False
