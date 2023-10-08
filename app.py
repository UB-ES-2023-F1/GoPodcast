from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import re

from models import User

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('POSTGRES_URL')
db = SQLAlchemy(app)


@app.route('/')
def hello_world():  # put application's code here
    return 'Hello World!' 


@app.post("/user")
def create_user():
    data_dict = request.get_json()

    username = data_dict['username']
    email = data_dict['email']
    password = data_dict['password']

    if not username or not email:
        return jsonify({'mensaje': 'Username and email are required'}), 400

    # Check if the user with the same username or email already exists
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({'mensaje': 'Username already exists'}), 400

    existing_email = User.query.filter_by(email=email).first()
    if existing_email:
        return jsonify({'mensaje': 'Email already exists'}), 400

    # check if email is valid
    email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    if not re.match(email_pattern, email):
        return jsonify({'mensaje': 'Email address not valid'}), 400

    # check if password is valid
    password_pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{6,}$'
    if not re.match(password_pattern, password):
        return jsonify({'mensaje': 'Contraseña no válida. La contraseña debe tener ' \
                                   'como mínimo 6 caracteres, entre los cuales debe ' \
                                   'haber almenos una letra, un número y una mayúscula'}), 400

    # Create a new user
    new_user = User(username=username, email=email)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'mensaje': 'Usuario creado correctamente'}), 201



if __name__ == '__main__':
    app.run()
