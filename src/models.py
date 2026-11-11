"""Basic domain models for the mutual fund order processing system."""

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum


class SchemeType(Enum):
    """The broad investment category of a mutual fund scheme."""

    EQUITY = "EQUITY"
    DEBT = "DEBT"
    LIQUID = "LIQUID"


class OrderType(Enum):
    """The kind of transaction requested by an investor."""

    PURCHASE = "PURCHASE"
    REDEMPTION = "REDEMPTION"
    SWITCH = "SWITCH"
    SIP = "SIP"
    SWITCH_OUT = "SWITCH_OUT"
    SWITCH_IN = "SWITCH_IN"
    SIP_PURCHASE = "SIP_PURCHASE"


class OrderStatus(Enum):
    """The current processing stage of an order."""

    RECEIVED = "RECEIVED"
    VALIDATED = "VALIDATED"
    PROCESSED = "PROCESSED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    ACCEPTED = "ACCEPTED"


@dataclass
class Scheme:
    """A mutual fund scheme registered in the system."""

    scheme_id: str
    name: str
    scheme_type: SchemeType
    elss: bool = False
    cutoff_time: time = time(15, 0)
    min_first_purchase: Decimal = Decimal("5000.00")
    min_additional: Decimal = Decimal("1000.00")
    min_sip: Decimal = Decimal("500.00")
    min_redemption: Decimal = Decimal("1000.00")


@dataclass
class Investor:
    """A person who places mutual fund orders."""

    investor_id: str
    name: str


@dataclass
class Folio:
    """An investor folio holding accounts in mutual fund schemes."""

    folio_id: str
    investor_name: str
    pan: str
    mobile: str
    bank_account: str
    ifsc: str
    opened_date: date


@dataclass
class Order:
    """An investor's request to buy, redeem, switch, or start a SIP."""

    order_id: str
    investor_id: str
    scheme_id: str
    order_type: OrderType
    amount: Decimal
    received_at: datetime
    status: OrderStatus = OrderStatus.RECEIVED


@dataclass
class InvestmentLot:
    """Units acquired in one investment transaction."""

    lot_id: str
    investor_id: str
    scheme_id: str
    purchase_date: date
    units: Decimal
    purchase_nav: Decimal

    @property
    def folio_id(self) -> str:
        """Alias for investor_id for folio compatibility."""
        return self.investor_id

    @property
    def allotment_date(self) -> date:
        """Alias for purchase_date for allotment compatibility."""
        return self.purchase_date


@dataclass
class ExitLoadSchedule:
    """Exit-load schedule band for a scheme type."""

    scheme_type: SchemeType
    from_day: int
    to_day: int
    load_pct: Decimal


@dataclass
class SIP:
    """A Systematic Investment Plan record."""

    sip_id: str
    folio_id: str
    scheme_id: str
    amount: Decimal
    sip_day: int
    registered_date: date
    status: str = "ACTIVE"
    consecutive_failures: int = 0
    paused_until_month: str | None = None
    paused_months: set[str] = field(default_factory=set)
    paused_years: set[int] = field(default_factory=set)
