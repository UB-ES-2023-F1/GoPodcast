from unittest.mock import ANY

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from models import Follow, Podcast, User, db


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
        user1 = User(
            email="test1@example.com",
            username="test1",
            password=generate_password_hash("Test1234"),
            verified=True,
        )
        user2 = User(
            email="test2@example.com",
            username="test2",
            password=generate_password_hash("Test1234"),
            verified=True,
        )
        user3 = User(
            email="test3@example.com",
            username="test3",
            password=generate_password_hash("Test1234"),
            verified=True,
        )
        db.session.add_all([user1, user2, user3])
        db.session.commit()
        podcast = Podcast(
            cover=b"",
            name="podcast",
            summary="summary",
            description="description",
            id_author=user2.id,
        )
        db.session.add(podcast)
        db.session.commit()
        follow = Follow(id_follower=user1.id, id_followed=user2.id)
        db.session.add(follow)
        db.session.commit()
        yield {
            "id_user1": user1.id,
            "id_user2": user2.id,
            "id_user3": user3.id,
            "id_podcast": podcast.id,
        }


def test_get_follows(app, data):
    client = app.test_client()

    # Unauthenticated
    response = client.get("/follows")
    assert response.status_code == 401

    # Authenticated
    response = client.post(
        "/login", json={"email": "test1@example.com", "password": "Test1234"}
    )
    assert response.status_code == 200
    expected_response = [
        {
            "id": str(data["id_user2"]),
            "username": "test2",
        }
    ]
    response = client.get("/follows")
    assert response.status_code == 200
    assert response.json == expected_response


def test_post_follow(app, data):
    client = app.test_client()

    # Unauthenticated
    response = client.post(f"/follows", json={"id": str(data["id_user3"])})
    assert response.status_code == 401

    # Authenticated
    response = client.post(
        "/login", json={"email": "test1@example.com", "password": "Test1234"}
    )
    assert response.status_code == 200
    response = client.post(f"/follows", json={"id": str(data["id_user3"])})
    assert response.status_code == 201

    # Already followed
    response = client.post(f"/follows", json={"id": str(data["id_user3"])})
    assert response.status_code == 400

    # User not found
    response = client.post(
        f"/follows", json={"id": "00000000-0000-0000-0000-000000000000"}
    )
    assert response.status_code == 404


def test_delete_follow(app, data):
    client = app.test_client()

    # Unauthenticated
    response = client.delete(f"/follows/{data['id_user2']}")
    assert response.status_code == 401

    # Authenticated
    response = client.post(
        "/login", json={"email": "test1@example.com", "password": "Test1234"}
    )
    assert response.status_code == 200
    response = client.delete(f"/follows/{data['id_user2']}")
    assert response.status_code == 200

    # Not followed
    response = client.delete(f"/follows/{data['id_user2']}")
    assert response.status_code == 400


def test_new_podcast_notification(app, data):
    client = app.test_client()

    # Unauthenticated
    response = client.get("/notifications")
    assert response.status_code == 401

    # Create new podcast by followed user
    response = client.post(
        "/login", json={"email": "test2@example.com", "password": "Test1234"}
    )
    assert response.status_code == 200
    body = {
        "name": "Nice podcast",
        "description": "Very nice podcast!",
        "summary": "breve resumen aquí",
        "cover": (b"", "test.jpg", "image/jpeg"),
        "category": "Other",
    }
    response = client.post("/podcasts", data=body)
    assert response.status_code == 201

    # Check notification from follower user
    response = client.post(
        "/login", json={"email": "test1@example.com", "password": "Test1234"}
    )
    assert response.status_code == 200
    expected_response = [
        {
            "id": ANY,
            "type": "new_podcast",
            "object": {
                "id": ANY,
                "name": "Nice podcast",
                "summary": "breve resumen aquí",
                "description": "Very nice podcast!",
            },
            "created_at": ANY,
        }
    ]
    response = client.get("/notifications")
    assert response.status_code == 200
    assert response.json == expected_response


def test_new_episode_notification(app, data):
    client = app.test_client()

    # Create new episode by followed user
    response = client.post(
        "/login", json={"email": "test2@example.com", "password": "Test1234"}
    )
    assert response.status_code == 200
    body = {
        "title": "title",
        "description": "description",
        "audio": (b"", "test.mp3", "audio/mpeg"),
    }
    response = client.post(f"/podcasts/{data['id_podcast']}/episodes", data=body)
    assert response.status_code == 201

    # Check notification from follower user
    response = client.post(
        "/login", json={"email": "test1@example.com", "password": "Test1234"}
    )
    assert response.status_code == 200
    expected_response = [
        {
            "id": ANY,
            "type": "new_episode",
            "object": {
                "id": ANY,
                "title": "title",
                "description": "description",
                "id_podcast": str(data["id_podcast"]),
            },
            "created_at": ANY,
        }
    ]
    response = client.get("/notifications")
    assert response.status_code == 200
    assert response.json == expected_response

    # Clear notifications
    response = client.delete("/notifications")
    assert response.status_code == 200
    response = client.get("/notifications")
    assert response.status_code == 200
    assert response.json == []
