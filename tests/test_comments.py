from unittest.mock import ANY

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from models import Comment, Episode, Podcast, User, db


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
        db.session.add_all([user1, user2])
        db.session.commit()
        podcast = Podcast(
            cover=b"",
            name="podcast",
            summary="summary",
            description="description",
            id_author=user1.id,
        )
        db.session.add(podcast)
        db.session.commit()
        episode = Episode(
            audio=b"",
            title="episode",
            description="description",
            id_podcast=podcast.id,
        )
        db.session.add(episode)
        db.session.commit()
        comment1 = Comment(content="comment1", id_user=user1.id, id_episode=episode.id)
        comment2 = Comment(content="comment2", id_user=user1.id, id_episode=episode.id)
        comment3 = Comment(content="comment3", id_user=user2.id, id_episode=episode.id)
        db.session.add_all([comment1, comment2, comment3])
        db.session.commit()
        yield {
            "id_user1": user1.id,
            "id_user2": user2.id,
            "id_podcast": podcast.id,
            "id_episode": episode.id,
            "id_comment1": comment1.id,
            "id_comment2": comment2.id,
            "id_comment3": comment3.id,
        }


def test_get_comments(app, data):
    client = app.test_client()

    response = client.get(f"/episodes/{data['id_episode']}/comments")
    assert response.status_code == 200
    expected_response = [
        {
            "id": str(data["id_comment1"]),
            "content": "comment1",
            "created_at": ANY,
            "id_episode": str(data["id_episode"]),
            "id_user": str(data["id_user1"]),
            "user": {
                "id": str(data["id_user1"]),
                "username": "test1",
            },
        },
        {
            "id": str(data["id_comment2"]),
            "content": "comment2",
            "created_at": ANY,
            "id_episode": str(data["id_episode"]),
            "id_user": str(data["id_user1"]),
            "user": {
                "id": str(data["id_user1"]),
                "username": "test1",
            },
        },
        {
            "id": str(data["id_comment3"]),
            "content": "comment3",
            "created_at": ANY,
            "id_episode": str(data["id_episode"]),
            "id_user": str(data["id_user2"]),
            "user": {
                "id": str(data["id_user2"]),
                "username": "test2",
            },
        },
    ]
    assert sorted(response.json, key=lambda x: x["content"]) == expected_response


def test_post_comment(app, data):
    client = app.test_client()

    # Unauthenticated
    response = client.post(
        f"/episodes/{data['id_episode']}/comments",
        json={"content": "comment"},
    )
    assert response.status_code == 401

    # Authenticated
    response = client.post(
        "/login", json={"email": "test1@example.com", "password": "Test1234"}
    )
    assert response.status_code == 200
    response = client.post(
        f"/episodes/{data['id_episode']}/comments",
        json={"content": "comment"},
    )
    assert response.status_code == 201

    # Episode not found
    response = client.post(
        f"/episodes/00000000-0000-0000-0000-000000000000/comments",
        json={"content": "comment"},
    )
    assert response.status_code == 404

    # Missing content
    response = client.post(
        f"/episodes/{data['id_episode']}/comments",
        json={},
    )
    assert response.status_code == 400


def test_delete_comment(app, data):
    client = app.test_client()

    # Unauthenticated
    response = client.delete(f"/comments/{data['id_comment1']}")
    assert response.status_code == 401

    # Authenticated
    response = client.post(
        "/login", json={"email": "test1@example.com", "password": "Test1234"}
    )
    assert response.status_code == 200
    response = client.delete(f"/comments/{data['id_comment1']}")
    assert response.status_code == 200

    # Alternative endpoint
    reseponse = client.delete(
        f"/episodes/{data['id_episode']}/comments/{data['id_comment2']}"
    )
    assert reseponse.status_code == 200

    # Comment not found
    response = client.delete(f"/comments/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

    # Comment not owned by user
    response = client.delete(f"/comments/{data['id_comment3']}")
    assert response.status_code == 403
