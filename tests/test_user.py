import pytest

from app import create_app
from models import db


@pytest.fixture
def client():
    app = create_app(testing=True)
    client = app.test_client()
    with app.app_context():
        db.create_all()
    yield client
    with app.app_context():
        db.drop_all()


def test_create_user(client):
    ###############
    # Usuario correcto
    ###############

    data = {
        "username": "SusanaOria2",
        "email": "susan@gmail.com",
        "password": "Contra1segura"
    }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 201
    # Assert the response content
    expected_response = {
        "mensaje": f"Usuario {data['username']} registrado correctamente"}
    assert response.get_json() == expected_response

    ###############
    # Usuario sin nombre
    ###############

    data = {
        "username": "",
        "email": "susan@gmail.com",
        "password": "Contra1segura"
    }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 400
    # Assert the response content
    expected_response = {
        'mensaje': 'Se requiere introducir usuario y contraseña'}
    assert response.get_json() == expected_response

    ###############
    # Usuario con nombre existente
    ###############

    data = {
        "username": "SusanaOria2",
        "email": "susanaaaaa@gmail.com",
        "password": "Contra2segura"
    }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 400
    # Assert the response content
    expected_response = {'mensaje': 'Nombre de usuario ya existente'}
    assert response.get_json() == expected_response

    ###############
    # Usuario con email existente
    ###############

    data = {
        "username": "PedroOrio",
        "email": "susan@gmail.com",
        "password": "Contra2segura"
    }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 400
    # Assert the response content
    expected_response = {'mensaje': 'Dirección email ya existente'}
    assert response.get_json() == expected_response

    ###############
    # Usuario con email no valido
    ###############

    data = {
        "username": "PedroOrio",
        "email": "susangmail.com",
        "password": "Contra2segura"
    }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 400
    # Assert the response content
    expected_response = {'mensaje': 'Dirección email no válida'}
    assert response.get_json() == expected_response

    data = {
        "username": "PedroOrio",
        "email": "susan@gmailcom",
        "password": "Contra2segura"
    }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 400
    # Assert the response content
    expected_response = {'mensaje': 'Dirección email no válida'}
    assert response.get_json() == expected_response

    data = {
        "username": "PedroOrio",
        "email": "@gmail.com",
        "password": "Contra2segura"
    }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 400
    # Assert the response content
    expected_response = {'mensaje': 'Dirección email no válida'}
    assert response.get_json() == expected_response

    ###############
    # Usuario con contraseña no válida
    ###############

    data = {
        "username": "SusanaOria2",
        "email": "susan@gmail.com",
        "password": "Ca1"
    }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 400
    # Assert the response content
    expected_response = {'mensaje': 'Contraseña no válida. La contraseña debe tener '
                         'como mínimo 6 caracteres, entre los cuales debe '
                         'haber almenos una letra, un número y una mayúscula'}
    assert response.get_json() == expected_response

    data = {
        "username": "SusanaOria2",
        "email": "susan@gmail.com",
        "password": "Contrasegura"
    }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 400
    # Assert the response content
    expected_response = {'mensaje': 'Contraseña no válida. La contraseña debe tener '
                         'como mínimo 6 caracteres, entre los cuales debe '
                         'haber almenos una letra, un número y una mayúscula'}
    assert response.get_json() == expected_response

    data = {
        "username": "SusanaOria2",
        "email": "susan@gmail.com",
        "password": "contra1segura"
    }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 400
    # Assert the response content
    expected_response = {'mensaje': 'Contraseña no válida. La contraseña debe tener '
                         'como mínimo 6 caracteres, entre los cuales debe '
                         'haber almenos una letra, un número y una mayúscula'}
    assert response.get_json() == expected_response

    data = {
        "username": "SusanaOria2",
        "email": "susan@gmail.com",
        "password": "1234567"
    }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 400
    # Assert the response content
    expected_response = {'mensaje': 'Contraseña no válida. La contraseña debe tener '
                         'como mínimo 6 caracteres, entre los cuales debe '
                         'haber almenos una letra, un número y una mayúscula'}
    assert response.get_json() == expected_response


def test_auth(client):

    data = {
        "username": "test",
        "email": "test@example.com",
        "password": "Test1234"
    }

    response = client.post('/user', json=data)

    # Wrong login details
    response = client.post('/login', json={"email": "test@example.com",
                                           "password": "wrong"})
    assert response.status_code == 401

    # Correct login details
    response = client.post('/login', json=data)
    assert response.status_code == 200

    # Access to protected route with auth
    response = client.get('/protected')
    assert response.status_code == 200

    # Logout
    response = client.post('/logout')
    assert response.status_code == 200

    # Access to protected route without auth
    response = client.get('/protected')
    assert response.status_code == 401
