import pytest
from app import create_app


@pytest.fixture
def client():
    return create_app({'TESTING': True}).test_client()


@pytest.mark.parametrize('age', [0,25,130])
def test_valid(client, age):
    response = client.post('/users', json={'name':'  Ana  ','email':'  ana@example.com  ','age':age})
    assert response.status_code == 201
    assert response.json == {'id':1,'name':'Ana','email':'ana@example.com','age':age}


@pytest.mark.parametrize('field,value', [('name',''),('name','a'),('name','x'*81),('name',None),('name',5),('email','invalid'),('email','a@@b'),('email','@b'),('email','a@'),('email','a b@c'),('email','a@b\tc'),('email',None),('email',3),('age',-1),('age',131),('age',True),('age',25.0),('age','25'),('age',None)])
def test_invalid_and_no_side_effect(client, field, value):
    payload = {'name':'Ana','email':'a@b','age':25}
    payload[field] = value
    response = client.post('/users', json=payload)
    assert response.status_code == 400
    assert isinstance(response.json.get('error'), str)
    store = client.application.extensions['store']
    assert store.users == []
    assert store.next_user_id == 1


@pytest.mark.parametrize('field', ['name','email','age'])
def test_missing(client, field):
    data = {'name':'Ana','email':'a@b','age':25}
    del data[field]
    assert client.post('/users',json=data).status_code == 400
    assert client.application.extensions['store'].users == []
