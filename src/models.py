"""Basic domain models for the mutual fund order processing system."""

from dataclasses import dataclass
from datetime import date, datetime
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


class OrderStatus(Enum):
    """The current processing stage of an order."""

    RECEIVED = "RECEIVED"
    VALIDATED = "VALIDATED"
    PROCESSED = "PROCESSED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


@dataclass
class Scheme:
    """A mutual fund scheme registered in the system."""

    scheme_id: str
    name: str
    scheme_type: SchemeType


@dataclass
class Investor:
    """A person who places mutual fund orders."""

    investor_id: str
    name: str


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
