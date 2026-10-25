import pytest
from app import create_app


@pytest.fixture
def client():
    return create_app({'TESTING': True}).test_client()


@pytest.mark.parametrize('query,page,size,ids,total_pages', [('',1,20,list(range(1,13)),1),('?page=1&page_size=5',1,5,[1,2,3,4,5],3),('?page=2&page_size=5',2,5,[6,7,8,9,10],3),('?page=3&page_size=5',3,5,[11,12],3),('?page=4&page_size=5',4,5,[],3),('?page_size=100',1,100,list(range(1,13)),1)])
def test_pages(client, query, page, size, ids, total_pages):
    response = client.get('/products'+query)
    assert response.status_code == 200
    payload = response.json
    assert payload == {'items': [{'id': i, 'name': f'Produto {i:02d}', 'price_cents': i*1000} for i in ids], 'total': 12, 'page': page, 'page_size': size, 'total_pages': total_pages}
    assert len(client.application.extensions['store'].products) == 12


@pytest.mark.parametrize('query', ['page=0','page=-1','page=1.5','page=abc','page=','page=%D9%A1','page_size=0','page_size=-2','page_size=101','page_size=','page_size=2.5'])
def test_invalid(client, query):
    response = client.get('/products?'+query)
    assert response.status_code == 400
    assert isinstance(response.json.get('error'), str)


def test_empty(client):
    client.application.extensions['store'].products.clear()
    assert client.get('/products').json == {'items': [], 'total': 0, 'page': 1, 'page_size': 20, 'total_pages': 0}
