import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from models import Favorite, Podcast, User, db


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
        podcast1 = Podcast(
            cover=b"",
            name="podcast1",
            summary="summary1",
            description="description1",
            category="category1",
            id_author=user.id,
        )
        podcast2 = Podcast(
            cover=b"",
            name="podcast2",
            summary="summary2",
            description="description2",
            category="category2",
            id_author=user.id,
        )
        podcast3 = Podcast(
            cover=b"",
            name="podcast3",
            summary="summary3",
            description="description3",
            category="category3",
            id_author=user.id,
        )
        db.session.add_all([podcast1, podcast2, podcast3])
        db.session.commit()
        entry1 = Favorite(id_user=user.id, id_podcast=podcast1.id)
        entry2 = Favorite(id_user=user.id, id_podcast=podcast2.id)
        db.session.add_all([entry1, entry2])
        db.session.commit()
        yield {
            "id_user": user.id,
            "id_podcast1": podcast1.id,
            "id_podcast2": podcast2.id,
            "id_podcast3": podcast3.id,
        }


def test_get_favorites(app, data):
    client = app.test_client()

    # Unauthenticated
    response = client.get("/favorites")
    assert response.status_code == 401

    # Authenticated
    response = client.post(
        "/login", json={"email": "test@example.com", "password": "Test1234"}
    )
    assert response.status_code == 200
    expected_response = [
        {
            "id": str(data["id_podcast1"]),
            "name": "podcast1",
            "description": "description1",
            "summary": "summary1",
            "cover": f"/podcasts/{data['id_podcast1']}/cover",
            "id_author": str(data["id_user"]),
            "category": "category1",
            "author": {
                "id": str(data["id_user"]),
                "username": "test",
            },
        },
        {
            "id": str(data["id_podcast2"]),
            "name": "podcast2",
            "description": "description2",
            "summary": "summary2",
            "cover": f"/podcasts/{data['id_podcast2']}/cover",
            "id_author": str(data["id_user"]),
            "category": "category2",
            "author": {
                "id": str(data["id_user"]),
                "username": "test",
            },
        },
    ]
    response = client.get("/favorites")
    assert response.status_code == 200
    assert response.json == expected_response


def test_post_favorites(app, data):
    client = app.test_client()

    # Unauthenticated
    response = client.post("/favorites", json={"id": str(data["id_podcast3"])})
    assert response.status_code == 401

    # Authenticated
    response = client.post(
        "/login", json={"email": "test@example.com", "password": "Test1234"}
    )
    assert response.status_code == 200
    response = client.post("/favorites", json={"id": str(data["id_podcast3"])})
    assert response.status_code == 201

    # Podcast already in favorites
    response = client.post("/favorites", json={"id": str(data["id_podcast3"])})
    assert response.status_code == 400

    # Podcast not found
    response = client.post(
        "/favorites", json={"id": "00000000-0000-0000-0000-000000000000"}
    )
    assert response.status_code == 404


def test_delete_favorites(app, data):
    client = app.test_client()

    # Unauthenticated
    response = client.delete(f"/favorites/{data['id_podcast1']}")
    assert response.status_code == 401

    # Authenticated
    response = client.post(
        "/login", json={"email": "test@example.com", "password": "Test1234"}
    )
    assert response.status_code == 200
    response = client.delete(f"/favorites/{data['id_podcast1']}")
    assert response.status_code == 200

    # Podcast not in favorites
    response = client.delete(f"/favorites/{data['id_podcast1']}")
    assert response.status_code == 404
