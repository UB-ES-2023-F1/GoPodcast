import os
import re
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request
from flask_jwt_extended import (JWTManager, create_access_token, get_jwt,
                                get_jwt_identity, jwt_required,
                                set_access_cookies, unset_jwt_cookies)
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from database import engine
from models import Base, User

app = Flask(__name__)
app.config['JWT_TOKEN_LOCATION'] = ['cookies', 'headers']
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config["JWT_SECRET_KEY"] = os.getenv('JWT_SECRET_KEY')
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
jwt = JWTManager(app)


@app.route('/')
def hello_world():  # put application's code here
    return 'Hello World!'


@app.route('/init_db')
def init_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return "DB initialized"


@app.post('/user')
def create_user():
    data_dict = request.get_json()

    username = data_dict['username']
    email = data_dict['email']
    password = data_dict['password']

    if not username or not email:
        return jsonify({'mensaje': 'Se requiere introducir usuario y contraseña'}), 400

    # check if email is valid
    email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    if not re.match(email_pattern, email):
        return jsonify({'mensaje': 'Dirección email no válida'}), 400

    # check if password is valid
    password_pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{6,}$'
    if not re.match(password_pattern, password):
        return jsonify({'mensaje': 'Contraseña no válida. La contraseña debe tener '
                                   'como mínimo 6 caracteres, entre los cuales debe '
                                   'haber almenos una letra, un número y una mayúscula'}), 400

    with Session(engine) as session:
        # Check if the user with the same username or email already exists
        existing_user = session.query(
            User).filter_by(username=username).first()
        if existing_user:
            return jsonify({'mensaje': 'Nombre de usuario ya existente'}), 400

        existing_email = session.query(User).filter_by(email=email).first()
        if existing_email:
            return jsonify({'mensaje': 'Dirección email ya existente'}), 400

        # Create a new user
        new_user = User(username=username, email=email,
                        password=generate_password_hash(password))
        session.add(new_user)
        session.commit()

        return jsonify({'mensaje': 'Usuario '+username+' registrado correctamente'}), 201

    return jsonify({'mensaje': 'Error'}), 400


@app.post('/login')
def login_user():
    data = request.get_json()
    email = data['email']
    password = data['password']

    with Session(engine) as session:
        user = session.query(User).filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            return jsonify({'success': False, 'error': 'Login details are incorrect'}), 401
        access_token = create_access_token(identity=user.id)
        resp = jsonify({'success': True})
        set_access_cookies(resp, access_token)
        return resp, 200


@app.post("/logout")
def logout():
    response = jsonify({'success': True})
    unset_jwt_cookies(response)
    return response
        return jsonify({'success': True}), 200


if __name__ == '__main__':
    app.run()
