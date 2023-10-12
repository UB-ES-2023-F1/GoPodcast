import json

import pytest

from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    client = app.test_client()
    yield client


def test_create_user(client):
    data = {
        'username': 'testuser',
        'email': 'testuser@example.com',
        'password': 'TestPassword1'
    }

    response = client.post('http://127.0.0.1:5000/user', data=json.dumps(data))

    assert response.status_code == 201  # Assuming a successful creation returns 201
    assert 'Usuario testuser registrado correctamente' in response.get_data(as_text=True)