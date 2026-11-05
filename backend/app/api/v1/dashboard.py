from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, Optional
from app.services.cache import get_revenue_summary
from app.services.reservations import PropertyNotFound, RevenueDataUnavailable, list_properties
from app.core.auth import authenticate_request as get_current_user

router = APIRouter()

def _require_tenant(current_user) -> str:
    """Every query is scoped by tenant, so a user without one can't be given any data."""
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Your account is not linked to a client.")
    return tenant_id

@router.get("/properties")
async def get_properties(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:

    tenant_id = _require_tenant(current_user)

    try:
        items = await list_properties(tenant_id)
    except RevenueDataUnavailable:
        raise HTTPException(status_code=503, detail="Property data is temporarily unavailable. Please try again shortly.")

    return {"items": items, "total": len(items)}

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    
    tenant_id = _require_tenant(current_user)

    if (month is None) != (year is None):
        raise HTTPException(status_code=400, detail="Send month and year together, or neither.")
    
    try:
        revenue_data = await get_revenue_summary(property_id, tenant_id, month, year)
    except PropertyNotFound:
        # Same body for an unknown property and another tenant's, so this doesn't reveal which IDs exist
        raise HTTPException(status_code=404, detail="Property not found.")
    except RevenueDataUnavailable:
        raise HTTPException(status_code=503, detail="Revenue data is temporarily unavailable. Please try again shortly.")
    
    # Round before converting: a float can't hold the exact value, so half-up is only reliable on the Decimal
    total_revenue_float = float(Decimal(revenue_data["total"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    
    return {
        "property_id": revenue_data['property_id'],
        "total_revenue": total_revenue_float,
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count']
    }
