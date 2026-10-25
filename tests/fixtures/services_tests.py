import pytest
from app.services import shipping_cost, loyalty_points, normalize_coupon


@pytest.mark.parametrize('subtotal,expected', [(0,1500),(19999,1500),(20000,0),(20001,0)])
def test_shipping(subtotal, expected):
    assert shipping_cost(subtotal) == expected


@pytest.mark.parametrize('subtotal,expected', [(0,0),(999,0),(1000,1),(1999,1)])
def test_points(subtotal, expected):
    assert loyalty_points(subtotal) == expected


@pytest.mark.parametrize('value', [-1,True,1.0,'1',None])
def test_invalid_subtotal(value):
    for function in [shipping_cost,loyalty_points]:
        with pytest.raises(ValueError):
            function(value)


@pytest.mark.parametrize('value,expected', [(' abc ','ABC'),('ABCDEFGHIJKL','ABCDEFGHIJKL'),('a1b','A1B')])
def test_coupon(value,expected):
    assert normalize_coupon(value) == expected


@pytest.mark.parametrize('value', ['','ab','a'*13,'ab c','a-b','abé',None,5])
def test_bad_coupon(value):
    with pytest.raises(ValueError):
        normalize_coupon(value)
