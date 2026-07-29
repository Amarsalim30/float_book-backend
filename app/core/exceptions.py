"""
Domain exceptions for Fpesa business logic.

These are raised in service/domain layers and must NOT import from FastAPI.
Routers are responsible for mapping them to appropriate HTTP responses.
"""


class FpesaError(Exception):
    """Base class for all Fpesa domain errors."""


class InsufficientTrackedBalanceError(FpesaError):
    """Raised when a Get Money Back amount exceeds the current tracked balance."""

    def __init__(self, name: str, requested: float, available: float) -> None:
        self.name = name
        self.requested = requested
        self.available = available
        super().__init__(
            f"Cannot get back {requested} from '{name}'. "
            f"Current balance is {available}."
        )


class TrackedAccountNotFoundError(FpesaError):
    """Raised when a TrackedAccount does not exist."""

    def __init__(self, account_id: int) -> None:
        self.account_id = account_id
        super().__init__(f"TrackedAccount {account_id} not found.")


class TrackedAccountOwnershipError(FpesaError):
    """Raised when a TrackedAccount does not belong to the business making the request."""

    def __init__(self, account_id: int) -> None:
        self.account_id = account_id
        super().__init__(
            f"TrackedAccount {account_id} does not belong to this business."
        )
