import pytest

from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    client = app.test_client()
    yield client


def test_create_user(client):
    # initialize db
    response = client.get('http://127.0.0.1:5000/init_db')

    ###############
    # Usuario correcto
    ###############

    data = {
            "username" : "SusanaOria2",
            "email" : "susan@gmail.com",
            "password" : "Contra1segura"
            }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 201
    # Assert the response content
    expected_response = {"mensaje": f"Usuario {data['username']} registrado correctamente"}
    assert response.get_json() == expected_response

    ###############
    # Usuario sin nombre
    ###############
    
    data = {
            "username" : "",
            "email" : "susan@gmail.com",
            "password" : "Contra1segura"
            }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 400
    # Assert the response content
    expected_response = {'mensaje': 'Se requiere introducir usuario y contraseña'}
    assert response.get_json() == expected_response

    ###############
    # Usuario con nombre existente
    ###############
    
    data = {
            "username" : "SusanaOria2",
            "email" : "susanaaaaa@gmail.com",
            "password" : "Contra2segura"
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
            "username" : "PedroOrio",
            "email" : "susan@gmail.com",
            "password" : "Contra2segura"
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
            "username" : "PedroOrio",
            "email" : "susangmail.com",
            "password" : "Contra2segura"
            }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 400
    # Assert the response content
    expected_response = {'mensaje': 'Dirección email no válida'}
    assert response.get_json() == expected_response

    data = {
            "username" : "PedroOrio",
            "email" : "susan@gmailcom",
            "password" : "Contra2segura"
            }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 400
    # Assert the response content
    expected_response = {'mensaje': 'Dirección email no válida'}
    assert response.get_json() == expected_response

    data = {
            "username" : "PedroOrio",
            "email" : "@gmail.com",
            "password" : "Contra2segura"
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
            "username" :"SusanaOria2",
            "email" : "susan@gmail.com",
            "password" : "Ca1"
            }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 400
    # Assert the response content
    expected_response = {'mensaje': 'Contraseña no válida. La contraseña debe tener ' \
                                   'como mínimo 6 caracteres, entre los cuales debe ' \
                                   'haber almenos una letra, un número y una mayúscula'}
    assert response.get_json() == expected_response

    data = {
            "username" :"SusanaOria2",
            "email" : "susan@gmail.com",
            "password" : "Contrasegura"
            }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 400
    # Assert the response content
    expected_response = {'mensaje': 'Contraseña no válida. La contraseña debe tener ' \
                                   'como mínimo 6 caracteres, entre los cuales debe ' \
                                   'haber almenos una letra, un número y una mayúscula'}
    assert response.get_json() == expected_response

    data = {
            "username" :"SusanaOria2",
            "email" : "susan@gmail.com",
            "password" : "contra1segura"
            }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 400
    # Assert the response content
    expected_response = {'mensaje': 'Contraseña no válida. La contraseña debe tener ' \
                                   'como mínimo 6 caracteres, entre los cuales debe ' \
                                   'haber almenos una letra, un número y una mayúscula'}
    assert response.get_json() == expected_response

    data = {
            "username" :"SusanaOria2",
            "email" : "susan@gmail.com",
            "password" : "1234567"
            }

    response = client.post('http://127.0.0.1:5000/user', json=data)

    # Assert the status code
    assert response.status_code == 400
    # Assert the response content
    expected_response = {'mensaje': 'Contraseña no válida. La contraseña debe tener ' \
                                   'como mínimo 6 caracteres, entre los cuales debe ' \
                                   'haber almenos una letra, un número y una mayúscula'}
    assert response.get_json() == expected_response
