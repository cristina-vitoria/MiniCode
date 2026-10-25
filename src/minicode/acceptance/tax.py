import pytest
from app.tax_service import calculate_tax


@pytest.mark.parametrize('subtotal,rate,expected', [(10000,10,1000),(1999,7,139),(0,100,0),(777,100,777),(777,0,0),(1,99,0)])
def test_tax(subtotal, rate, expected):
    result = calculate_tax(subtotal, rate)
    assert type(result) is int
    assert result == expected


@pytest.mark.parametrize('subtotal,rate', [(-1,1),(1,-1),(1,101),(True,1),(1,True),(1.0,1),(1,1.0),('1',1),(1,None)])
def test_invalid(subtotal, rate):
    with pytest.raises(ValueError):
        calculate_tax(subtotal, rate)
