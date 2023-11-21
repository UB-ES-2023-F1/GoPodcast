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

def test_search_perfect_match(app):
    with app.app_context():
        user = User(
            email="test@example.com",
            username="Carl Sagan",
            password=generate_password_hash("Test1234"),
            verified=True,
        )
        db.session.add(user)
        db.session.commit()
        id_user = user.id
        user = User(
            email="test2@example.com",
            username="Carlos Latre",
            password=generate_password_hash("Test1234"),
            verified=True,
        )
        db.session.add(user)
        db.session.commit()
        id_user2 = user.id
        user = User(
            email="test3@example.com",
            username="Andreu Buenafuente",
            password=generate_password_hash("Test1234"),
            verified=True,
        )
        db.session.add(user)
        db.session.commit()
        id_user3 = user.id
        podcast = Podcast(
            cover=b"",
            name="Programming for dummies",
            summary="summary",
            description="buenisimo",
            id_author=id_user,
        )
        db.session.add(podcast)
        db.session.commit()
        id_podcast = podcast.id
        podcast = Podcast(
            cover=b"",
            name="Programming for fun",
            summary="summary",
            description="buenisimo",
            id_author=id_user,
        )
        db.session.add(podcast)
        db.session.commit()
        id_podcast2 = podcast.id
        podcast = Podcast(
            cover=b"",
            name="Cooking master",
            summary="summary",
            description="buenisimo",
            id_author=id_user,
        )
        db.session.add(podcast)
        db.session.commit()
        id_podcast3 = podcast.id

    client = app.test_client()

    # search podcast by name, a perfect match
    response = client.get("/search/podcast/Programming for dummies")
    assert response.status_code == 201
    expected_response = [{
                            "id": str(id_podcast),
                            "id_author": str(id_user),
                            "author": {
                                "id": str(id_user),
                                "username": "Carl Sagan",
                            },
                            "cover" : f"/podcasts/{id_podcast}/cover",
                            "name" : "Programming for dummies",
                            "summary" : "summary",
                            "description" : "buenisimo",
                            "category": None,
                            "match_percentatge": 100
                        }]
    assert response.get_json() == expected_response

    # search author by username, perfect match
    response = client.get("/search/user/Carl Sagan")
    assert response.status_code == 201
    expected_response = [{
                            "id": str(id_user),
                            "username": "Carl Sagan",
                            "email": "test@example.com",
                            "verified": True,
                            "match_percentatge": 100
                        }]
    assert response.get_json() == expected_response

    # search by podcast, partial matches
    response = client.get("/search/podcast/Programin for dumies")
    assert response.status_code == 200
    expected_response = [
                            {
                                "id": str(id_podcast),
                                "id_author": str(id_user),
                                "author": {
                                    "id": str(id_user),
                                    "username": "Carl Sagan",
                                },
                                "cover" : f"/podcasts/{id_podcast}/cover",
                                "name" : "Programming for dummies",
                                "summary" : "summary",
                                "description" : "buenisimo",
                                "category": None,
                                "match_percentatge": 86.96
                            },
                            {
                                "id": str(id_podcast2),
                                "id_author": str(id_user),
                                "author": {
                                    "id": str(id_user),
                                    "username": "Carl Sagan",
                                },
                                "cover" : f"/podcasts/{id_podcast2}/cover",
                                "name" : "Programming for fun",
                                "summary" : "summary",
                                "description" : "buenisimo",
                                "category": None,
                                "match_percentatge": 65.00
                            }
                        ]
    assert response.get_json() == expected_response

    # search by user, partial matches
    response = client.get("/search/user/Carlos Sagan")
    assert response.status_code == 200
    expected_response = [
                            {
                                "id": str(id_user),
                                "username": "Carl Sagan",
                                "email": "test@example.com",
                                "verified": True,
                                "match_percentatge": 83.33
                            },
                            {
                                "id": str(id_user2),
                                "username": "Carlos Latre",
                                "email": "test2@example.com",
                                "verified": True,
                                "match_percentatge": 66.67
                            }
                        ]
    assert response.get_json() == expected_response

    # search by user, no good matches found
    response = client.get("/search/user/Pirlo")
    assert response.status_code == 404
    expected_response = {"message": "No good matches found"}
    assert response.get_json() == expected_response
