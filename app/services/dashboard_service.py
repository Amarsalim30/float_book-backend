from sqlalchemy.orm import Session
from app.schemas.dashboard import DashboardResponse


def get_dashboard(db: Session) -> DashboardResponse:
    # TODO: Calculate from ledger entries
    return DashboardResponse(
        cash=0,
        float=0,
        receivables=0,
        payables=0
    )
