from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List
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

async def calculate_monthly_revenue(property_id: str, month: int, year: int, db_session=None) -> Decimal:
    """
    Calculates revenue for a specific month.
    """

    start_date = datetime(year, month, 1)
    if month < 12:
        end_date = datetime(year, month + 1, 1)
    else:
        end_date = datetime(year + 1, 1, 1)
        
    print(f"DEBUG: Querying revenue for {property_id} from {start_date} to {end_date}")

    # SQL Simulation (This would be executed against the actual DB)
    query = """
        SELECT SUM(total_amount) as total
        FROM reservations
        WHERE property_id = $1
        AND tenant_id = $2
        AND check_in_date >= $3
        AND check_in_date < $4
    """
    
    # In production this query executes against a database session.
    # result = await db.fetch_val(query, property_id, tenant_id, start_date, end_date)
    # return result or Decimal('0')
    
    return Decimal('0') # Placeholder for now until DB connection is finalized

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
