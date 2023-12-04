import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from models import User, db


@pytest.fixture
def app():
    app = create_app(testing=True)
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture
def data(app):
    with app.app_context():
        user = User(
            email="test@example.com",
            username="test",
            password=generate_password_hash("Test1234"),
            verified=True,
        )
        db.session.add(user)
        db.session.commit()
        yield {
            "id_user": user.id,
        }


def test_preflight(app):
    client = app.test_client()
    res = client.options("/")
    assert res.status_code == 200
    assert res.headers["X-Content-Type-Options"] == "*"


def test_hello_world(app):
    client = app.test_client()
    res = client.get("/")
    assert res.status_code == 200
