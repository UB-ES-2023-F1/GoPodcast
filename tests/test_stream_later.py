import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from models import Episode, Podcast, StreamLater, User, db


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
        podcast = Podcast(
            cover=b"",
            name="podcast",
            summary="summary",
            description="description",
            id_author=user.id,
        )
        db.session.add(podcast)
        db.session.commit()
        episode1 = Episode(
            audio=b"",
            title="episode1",
            description="description1",
            id_podcast=podcast.id,
        )
        episode2 = Episode(
            audio=b"",
            title="episode2",
            description="description2",
            id_podcast=podcast.id,
        )
        episode3 = Episode(
            audio=b"",
            title="episode3",
            description="description3",
            id_podcast=podcast.id,
        )
        db.session.add_all([episode1, episode2, episode3])
        db.session.commit()
        entry1 = StreamLater(id_user=user.id, id_episode=episode1.id)
        entry2 = StreamLater(id_user=user.id, id_episode=episode2.id)
        db.session.add_all([entry1, entry2])
        db.session.commit()
        yield {
            "id_user": user.id,
            "id_podcast": podcast.id,
            "id_episode1": episode1.id,
            "id_episode2": episode2.id,
            "id_episode3": episode3.id,
        }


def test_get_stream_later(app, data):
    client = app.test_client()

    # Unauthenticated
    response = client.get("/stream_later")
    assert response.status_code == 401

    # Authenticated
    response = client.post(
        "/login", json={"email": "test@example.com", "password": "Test1234"}
    )
    assert response.status_code == 200
    expected_response = [
        {
            "id": str(data["id_episode1"]),
            "title": "episode1",
            "description": "description1",
            "id_podcast": str(data["id_podcast"]),
        },
        {
            "id": str(data["id_episode2"]),
            "title": "episode2",
            "description": "description2",
            "id_podcast": str(data["id_podcast"]),
        },
    ]
    response = client.get("/stream_later")
    assert response.status_code == 200
    assert response.get_json() == expected_response


def test_post_stream_later(app, data):
    client = app.test_client()

    # Unauthenticated
    response = client.post("/stream_later", json={"id": str(data["id_episode3"])})
    assert response.status_code == 401

    # Authenticated
    response = client.post(
        "/login", json={"email": "test@example.com", "password": "Test1234"}
    )
    assert response.status_code == 200
    response = client.post("/stream_later", json={"id": str(data["id_episode3"])})
    assert response.status_code == 201

    # Episode already in stream later
    response = client.post("/stream_later", json={"id": str(data["id_episode3"])})
    assert response.status_code == 400

    # Episode not found
    response = client.post(
        "/stream_later", json={"id": "00000000-0000-0000-0000-000000000000"}
    )
    assert response.status_code == 404


def test_delete_stream_later(app, data):
    client = app.test_client()

    # Unauthenticated
    response = client.delete(f"/stream_later/{data['id_episode1']}")
    assert response.status_code == 401

    # Authenticated
    response = client.post(
        "/login", json={"email": "test@example.com", "password": "Test1234"}
    )
    assert response.status_code == 200
    response = client.delete(f"/stream_later/{data['id_episode1']}")
    assert response.status_code == 200

    # Episode not in stream later
    response = client.delete(f"/stream_later/{data['id_episode1']}")
    assert response.status_code == 404
