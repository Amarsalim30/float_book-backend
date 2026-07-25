from pydantic import BaseModel


class DashboardResponse(BaseModel):
    cash: float
    float: float
    receivables: float
    payables: float
