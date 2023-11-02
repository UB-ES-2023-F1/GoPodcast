import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from models import Podcast, User, db


@pytest.fixture
def app():
    app = create_app(testing=True)
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.drop_all()

def test_post_episode(app):
    with app.app_context():
        user = User(
            email="carlo@gmail.com",
            username="Carl Sagan",
            password=generate_password_hash("Test1234"),
            verified=True
        )
        db.session.add(user)
        db.session.commit()

    client = app.test_client()

    data = {
        "name": "Nice podcast",
        "description": "Very nice podcast!",
        "cover": (b"", "test.jpg", "image/jpeg")
    }

    # Unauthenticated
    response = client.post("/podcasts", data=data)
    assert response.status_code == 401

    # Authenticated
    response = client.post('/login', json={"email": "carlo@gmail.com",
                                           "password": "Test1234"})
    assert response.status_code == 200
    response = client.post("/podcasts", data=data)
    assert response.status_code == 201


def test_post_episode(app):
    with app.app_context():
        user = User(
            email="test@example.com",
            username="test",
            password=generate_password_hash("Test1234"),
            verified=True
        )
        db.session.add(user)
        db.session.commit()
        podcast = Podcast(
            cover=b"",
            name="podcast",
            description="description",
            id_author=user.id
        )
        db.session.add(podcast)
        db.session.commit()
        id_podcast = podcast.id
    data = {
        "title": "title",
        "description": "description",
        "audio": (b"", "test.mp3", "audio/mpeg")
    }
    client = app.test_client()

    # Unauthenticated
    response = client.post(f"/podcasts/{id_podcast}/episodes", data=data)
    assert response.status_code == 401

    # Authenticated
    response = client.post('/login', json={"email": "test@example.com",
                                           "password": "Test1234"})
    assert response.status_code == 200
    response = client.post(f"/podcasts/{id_podcast}/episodes", data=data)
    assert response.status_code == 201
