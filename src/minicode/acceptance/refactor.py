import ast
from copy import deepcopy
from pathlib import Path
import pytest
from app import report_service as module


def expected(orders):
    result = {'revenue_cents':0,'units':0,'orders':0,'by_channel':{'retail':0,'wholesale':0}}
    for order in orders:
        if order['status'] != 'paid' or order['channel'] not in result['by_channel']:
            continue
        result['orders'] += 1
        for item in order['items']:
            if item['quantity'] > 0:
                value = item['price_cents'] * item['quantity']
                result['revenue_cents'] += value
                result['by_channel'][order['channel']] += value
                result['units'] += item['quantity']
    return result


@pytest.mark.parametrize('size', [0,1,2,5,20])
def test_equivalence(size):
    orders = [{'status': ['paid','pending','paid','cancelled'][i%4], 'channel':['retail','wholesale','unknown'][i%3],
               'items':[{'price_cents':i*123,'quantity':i%3},{'price_cents':0,'quantity':2}]} for i in range(size)]
    original = deepcopy(orders)
    assert module.build_sales_report(orders) == expected(orders)
    assert orders == original


def test_real_extraction(monkeypatch):
    tree = ast.parse(Path(module.__file__).read_text())
    functions = {node.name:node for node in tree.body if isinstance(node,ast.FunctionDef)}
    report = functions['build_sales_report']
    called = {node.func.id for node in ast.walk(report) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name)}
    helpers = called & (functions.keys() - {'build_sales_report'})
    assert helpers, 'Extraia e invoque uma função auxiliar de cálculo de itens'
    assert not any(isinstance(node,ast.Name) and node.id in {'a','b','x','y','w'} for node in ast.walk(report))
    # Uma única iteração principal; itens são processados pela função extraída.
    assert sum(isinstance(node,ast.For) for node in ast.walk(report)) <= 1
    observed = set()
    for helper in helpers:
        original = getattr(module,helper)
        def spy(*args, _original=original, _helper=helper, **kwargs):
            observed.add(_helper)
            return _original(*args,**kwargs)
        monkeypatch.setattr(module,helper,spy)
    for channel in ['retail','wholesale']:
        observed.clear()
        order = {'status':'paid','channel':channel,'items':[{'price_cents':100,'quantity':2}]}
        assert module.build_sales_report([order]) == expected([order])
        assert observed, 'Ambos os canais devem usar a função auxiliar'
