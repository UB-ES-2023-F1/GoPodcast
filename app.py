from flask import Flask
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import engine
from models import User, Base

app = Flask(__name__)


@app.route('/')
def hello_world():  # put application's code here
    return 'Hello World!'

@app.route('/test')
def test():
    with Session(engine) as session:
        new_user = User(email="example@example.com", password="hashed_qwerjpsadof")
        session.add(new_user)
        session.commit()
    stmt = select(User).where(User.email=="example@example.com")
    for user in session.scalars(stmt):
        print(user)
    return "test"


@app.route('/init_db')
def init_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return "DB initialized"



if __name__ == '__main__':
    app.run()
