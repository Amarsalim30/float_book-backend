from enum import Enum


class TransactionType(str, Enum):
    SALE = "sale"
    EXPENSE = "expense"
    WITHDRAWAL = "withdrawal"
    DEPOSIT = "deposit"
    ADD_FLOAT = "add_float"
    ADD_CASH = "add_cash"
    TRANSFER = "transfer"


class TransactionSource(str, Enum):
    MANUAL = "manual"
    IMPORTED_MPESA = "imported_mpesa"
    SYSTEM_GENERATED = "system_generated"


class AccountType(str, Enum):
    CASH = "cash"
    FLOAT = "float"
    TRACKED = "tracked"


class PaymentMethod(str, Enum):
    CASH = "cash"
    MPESA = "mpesa"


class LedgerEntryType(str, Enum):
    SEED = "seed"
    CREDIT = "credit"
    DEBIT = "debit"


class MpesaDirection(str, Enum):
    MONEY_RECEIVED = "MONEY_RECEIVED"
    MONEY_SENT = "MONEY_SENT"
    WITHDRAWAL = "WITHDRAWAL"
    REVERSAL = "REVERSAL"
