from copy import deepcopy
import pytest
from app.report_service import build_sales_report


def order(status="paid", channel="retail", items=None):
    return {"status": status, "channel": channel, "items": items if items is not None else []}


def test_empty_report():
    assert build_sales_report([]) == {
        "revenue_cents": 0, "units": 0, "orders": 0,
        "by_channel": {"retail": 0, "wholesale": 0},
    }


def test_mixed_orders_and_no_mutation():
    orders = [
        order(items=[{"price_cents": 500, "quantity": 2}, {"price_cents": 999, "quantity": 0}]),
        order(channel="wholesale", items=[{"price_cents": 300, "quantity": 3}]),
        order(status="cancelled", items=[{"price_cents": 10000, "quantity": 1}]),
        order(channel="unknown", items=[{"price_cents": 10000, "quantity": 1}]),
    ]
    before = deepcopy(orders)
    assert build_sales_report(orders) == {
        "revenue_cents": 1900, "units": 5, "orders": 2,
        "by_channel": {"retail": 1000, "wholesale": 900},
    }
    assert orders == before


@pytest.mark.parametrize("channel", ["retail", "wholesale"])
def test_paid_empty_order_counts(channel):
    result = build_sales_report([order(channel=channel)])
    assert result["orders"] == 1
    assert result["units"] == result["revenue_cents"] == 0


@pytest.mark.parametrize("status", ["pending", "cancelled", "refunded"])
def test_unpaid_orders_are_ignored(status):
    assert build_sales_report([order(status=status)])["orders"] == 0


def test_free_items_count_as_units():
    result = build_sales_report([order(items=[{"price_cents": 0, "quantity": 3}])])
    assert result["units"] == 3
    assert result["revenue_cents"] == 0
