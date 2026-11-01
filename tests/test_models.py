from datetime import datetime
from decimal import Decimal

from src.models import (
    InvestmentLot,
    Investor,
    Order,
    OrderStatus,
    OrderType,
    Scheme,
    SchemeType,
)


def test_scheme_can_be_created():
    scheme = Scheme("SCH001", "Sample Equity Fund", SchemeType.EQUITY)
    assert scheme.scheme_type == SchemeType.EQUITY


def test_investor_can_be_created():
    investor = Investor("INV001", "Sample Investor")
    assert investor.name == "Sample Investor"


def test_order_uses_decimal_amount_and_received_status_by_default():
    order = Order(
        "ORD001", "INV001", "SCH001", OrderType.PURCHASE,
        Decimal("1000.00"), datetime(2026, 1, 23, 14, 0),
    )
    assert order.amount == Decimal("1000.00")
    assert order.status == OrderStatus.RECEIVED


def test_investment_lot_uses_decimal_values():
    lot = InvestmentLot(
        "LOT001", "INV001", "SCH001", datetime(2026, 1, 23).date(),
        Decimal("10.5"), Decimal("95.25"),
    )
    assert lot.units == Decimal("10.5")
    assert lot.purchase_nav == Decimal("95.25")
