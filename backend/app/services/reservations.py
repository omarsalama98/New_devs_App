from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional
import logging
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.core.database_pool import db_pool

logger = logging.getLogger(__name__)

class RevenueDataUnavailable(Exception):
    """The database can't be reached, so no revenue figures can be given."""

class PropertyNotFound(Exception):
    """The property doesn't exist, or belongs to another tenant."""

async def _fetch_rows(query: str, params: Dict[str, Any]) -> List[Any]:
    """
    Runs a read query on the shared pool. Database failures become RevenueDataUnavailable.
    """
    if not db_pool.session_factory:
        await db_pool.initialize()

    # initialize() swallows its own errors and leaves session_factory as None
    if not db_pool.session_factory:
        raise RevenueDataUnavailable("Database pool not available")

    try:
        async with db_pool.get_session() as session:
            result = await session.execute(text(query), params)
            return result.fetchall()
    except (SQLAlchemyError, OSError) as e:  # A closed port or bad host raises OSError, not a SQLAlchemy error
        logger.error(f"Database error: {e}")
        raise RevenueDataUnavailable("Database query failed") from e

def _revenue_summary(rows: List[Any], property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Turns the single row from a revenue query into the summary dict. No row means the tenant doesn't own the property.
    """
    if not rows:
        raise PropertyNotFound(property_id)

    row = rows[0]
    total_revenue = Decimal(str(row.total_revenue))
    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": str(total_revenue),
        "currency": "USD",
        "count": row.reservation_count
    }

async def calculate_monthly_revenue(property_id: str, tenant_id: str, month: int, year: int) -> Dict[str, Any]:
    """
    Calculates revenue for a specific month of the property's local calendar.
    """

    start_date = datetime(year, month, 1)
    if month < 12:
        end_date = datetime(year, month + 1, 1)
    else:
        end_date = datetime(year + 1, 1, 1)

    # AT TIME ZONE turns the stored UTC instant into the property's local time, so the month is the one the guest saw
    # The bounds sit on the LEFT JOIN, not in WHERE, so an owned property with no bookings that month still gives a row with 0
    rows = await _fetch_rows("""
        SELECT
            p.id,
            COALESCE(SUM(r.total_amount), 0) as total_revenue,
            COUNT(r.id) as reservation_count
        FROM properties p
        LEFT JOIN reservations r ON r.property_id = p.id AND r.tenant_id = p.tenant_id
            AND (r.check_in_date AT TIME ZONE p.timezone) >= :start_date
            AND (r.check_in_date AT TIME ZONE p.timezone) < :end_date
        WHERE p.id = :property_id AND p.tenant_id = :tenant_id
        GROUP BY p.id
    """, {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "start_date": start_date,
        "end_date": end_date
    })

    return _revenue_summary(rows, property_id, tenant_id)

def calculate_trend_percent(current: Decimal, previous: Decimal) -> Optional[Decimal]:
    """
    Percentage change from the previous month to the current one. With no previous revenue there is nothing to compare with.
    """
    if previous == 0:
        return None

    return ((current - previous) / previous * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Aggregates revenue from database.
    """
    # LEFT JOIN: an owned property with no bookings gives one row with 0, a property the tenant doesn't own gives no row
    rows = await _fetch_rows("""
        SELECT
            p.id,
            COALESCE(SUM(r.total_amount), 0) as total_revenue,
            COUNT(r.id) as reservation_count
        FROM properties p
        LEFT JOIN reservations r ON r.property_id = p.id AND r.tenant_id = p.tenant_id
        WHERE p.id = :property_id AND p.tenant_id = :tenant_id
        GROUP BY p.id
    """, {
        "property_id": property_id,
        "tenant_id": tenant_id
    })

    return _revenue_summary(rows, property_id, tenant_id)

async def list_properties(tenant_id: str) -> List[Dict[str, str]]:
    """
    Lists the tenant's own properties.
    """
    rows = await _fetch_rows("""
        SELECT id, name
        FROM properties
        WHERE tenant_id = :tenant_id
        ORDER BY name
    """, {
        "tenant_id": tenant_id
    })

    return [{"id": row.id, "name": row.name} for row in rows]
