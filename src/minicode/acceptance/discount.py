import pytest
from app.cart_service import calculate_discount


@pytest.mark.parametrize('subtotal,percentage,expected', [(0,0,0),(10000,10,1000),(1999,15,299),(1,99,0),(12345,100,12345),(900,0,0)])
def test_discount(subtotal, percentage, expected):
    result = calculate_discount(subtotal, percentage)
    assert type(result) is int
    assert result == expected


@pytest.mark.parametrize('subtotal,percentage', [(-1,10),(10,-1),(10,101),(True,10),(10,False),(1.2,10),(10,2.5),('100',10),(10,'2'),(None,10),(10,None)])
def test_invalid(subtotal, percentage):
    with pytest.raises(ValueError):
        calculate_discount(subtotal, percentage)
