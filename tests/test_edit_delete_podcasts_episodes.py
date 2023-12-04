import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from models import Episode, Podcast, User, db


@pytest.fixture
def app():
    app = create_app(testing=True)
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.drop_all()


def test_edit_delete_podcasts_episodes(app):
    with app.app_context():
        user = User(
            email="test@example.com",
            username="Carl Sagan",
            password=generate_password_hash("Test123"),
            verified=True,
        )
        db.session.add(user)
        db.session.commit()
        id_user = user.id
        user = User(
            email="test2@example.com",
            username="Carlos Latre",
            password=generate_password_hash("Test456"),
            verified=True,
        )
        db.session.add(user)
        db.session.commit()
        id_user2 = user.id
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
            name="Coding for fun",
            summary="summary",
            description="buenisimo",
            id_author=id_user,
        )
        db.session.add(podcast)
        db.session.commit()
        id_podcast2 = podcast.id
        podcast = Podcast(
            cover=b"",
            name="Gaming for fun",
            summary="summary",
            description="buenisimo",
            id_author=id_user2,
        )
        db.session.add(podcast)
        db.session.commit()
        id_podcast3 = podcast.id
        episode = Episode(
            audio=b"",
            title="Episode1",
            description="how I met your father",
            id_podcast=id_podcast,
        )
        db.session.add(episode)
        db.session.commit()
        id_episode = episode.id
        episode = Episode(
            audio=b"",
            title="Episode2",
            description="how I met your mother",
            id_podcast=id_podcast,
        )
        db.session.add(episode)
        db.session.commit()
        id_episode2 = episode.id
        episode = Episode(
            audio=b"",
            title="Episode3",
            description="how I met your mother",
            id_podcast=id_podcast3,
        )
        db.session.add(episode)
        db.session.commit()
        id_episode3 = episode.id

    client = app.test_client()

    # search user by id
    response = client.get(f"/user/{id_user}")
    assert response.status_code == 201
    expected_response = {
        "name": "Carl Sagan",
        "bio": None,
        "type": "author",
    }
    assert response.get_json() == expected_response

    # get podcasts created by user
    response = client.get(f"/user/created_podcasts/{id_user}")
    assert response.status_code == 200
    expected_response = [
        {
            "id": str(id_podcast),
            "author": {
                "id": str(id_user),
                "username": "Carl Sagan",
            },
            "cover": f"/podcasts/{id_podcast}/cover",
            "name": "Programming for dummies",
            "summary": "summary",
            "description": "buenisimo",
            "category": None,
        },
        {
            "id": str(id_podcast2),
            "author": {
                "id": str(id_user),
                "username": "Carl Sagan",
            },
            "cover": f"/podcasts/{id_podcast2}/cover",
            "name": "Coding for fun",
            "summary": "summary",
            "description": "buenisimo",
            "category": None,
        },
    ]
    assert response.get_json() == expected_response
    podcast_data = {
        "name": "Nice podcast",
        "description": "Very nice podcast!",
        "category": "Other",
        "cover": (b"", "test.jpg", "image/jpeg"),
        "summary": "New summary",
    }

    episode_data = {
        "description": "I made the episode even better",
        "tags": "chill",
        "audio": (b"", "test.mp3", "audio/mpeg"),
        "title": "Episode1B",
    }

    client.post("/login", json={"email": "test2@example.com", "password": "Test456"})

    # try edit episode with a user that is not the author
    response = client.put(f"/episodes/{id_episode}", data=episode_data)
    assert response.status_code == 404
    expected_response = {"error": "User can only edit their own creations"}
    assert response.get_json() == expected_response

    client.post("/logout")
    client.post("/login", json={"email": "test@example.com", "password": "Test123"})

    bio_data = {"bio": "Soy un crack"}

    # change user's bio
    response = client.put(f"/user/bio", data=bio_data)
    assert response.status_code == 201
    expected_response = {"message": "Bio updated successfully"}
    assert response.get_json() == expected_response

    response = client.get(f"/user/{id_user}")
    assert response.status_code == 201
    expected_response = {
        "name": "Carl Sagan",
        "bio": "Soy un crack",
        "type": "author",
    }
    assert response.get_json() == expected_response

    # edit podcast
    response = client.put(f"/podcasts/{id_podcast}", data=podcast_data)
    assert response.status_code == 201
    expected_response = {"message": "Podcast updated successfully"}
    assert response.get_json() == expected_response

    # edit podcast with invalid data
    response = client.put(f"/podcasts/{id_podcast}", data={"category": "INVALID"})
    assert response.status_code == 401

    # Pocast not found
    response = client.put(f"/podcasts/00000000-0000-0000-0000-000000000000", data=podcast_data)
    assert response.status_code == 404

    # Podcast from another user
    response = client.put(f"/podcasts/{id_podcast3}", data=podcast_data)
    assert response.status_code == 404

    # Podcast name already exists
    response = client.put(f"/podcasts/{id_podcast2}", data=podcast_data)
    assert response.status_code == 400

    # edit episode
    response = client.put(f"/episodes/{id_episode}", data=episode_data)
    assert response.status_code == 201
    expected_response = {"message": "Episode updated successfully"}
    assert response.get_json() == expected_response

    # check if changes in podcast have been successfully applied
    response = client.get(f"/podcasts/{id_podcast}")
    assert response.status_code == 201
    expected_response = {
        "id": str(id_podcast),
        "description": "Very nice podcast!",
        "name": "Nice podcast",
        "summary": "New summary",
        "cover": f"/podcasts/{id_podcast}/cover",
        "id_author": str(id_user),
        "author": {
            "id": str(id_user),
            "username": "Carl Sagan",
        },
        "category": "Other",
    }
    assert response.get_json() == expected_response

    # check if changes in episode have been successfully applied
    response = client.get(f"/podcasts/{id_podcast}/episodes")
    assert response.status_code == 200
    expected_response = [
        {
            "id": str(id_episode2),
            "description": "how I met your mother",
            "title": "Episode2",
            "tags": [],
            "audio": f"/episodes/{id_episode2}/audio",
        },
        {
            "id": str(id_episode),
            "description": "I made the episode even better",
            "title": "Episode1B",
            "tags": ["chill"],
            "audio": f"/episodes/{id_episode}/audio",
        },
    ]
    assert response.get_json() == expected_response

    # edit episode not found
    response = client.put(f"/episodes/00000000-0000-0000-0000-000000000000", data=episode_data)
    assert response.status_code == 404

    # edit episode with same title as another episode
    response = client.put(f"/episodes/{id_episode}", data={"title": "Episode2"})
    assert response.status_code == 400

    # delete episode
    response = client.delete(f"/episodes/{id_episode2}")
    assert response.status_code == 200

    # check if episode has been deleted
    response = client.get(f"/podcasts/{id_podcast}/episodes")
    assert response.status_code == 200
    expected_response = [
        {
            "id": str(id_episode),
            "description": "I made the episode even better",
            "title": "Episode1B",
            "tags": ["chill"],
            "audio": f"/episodes/{id_episode}/audio",
        }
    ]
    assert response.get_json() == expected_response

    # delete episode that does not exist
    response = client.delete(f"/episodes/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

    # delete episode from another user
    response = client.delete(f"/episodes/{id_episode3}")
    assert response.status_code == 404

    # delete podcast
    response = client.delete(f"/podcasts/{id_podcast}")
    assert response.status_code == 200

    # check if podcast and the other episode have been deleted
    response = client.get(f"/user/created_podcasts/{id_user}")
    assert response.status_code == 200
    expected_response = [
        {
            "id": str(id_podcast2),
            "author": {
                "id": str(id_user),
                "username": "Carl Sagan",
            },
            "cover": f"/podcasts/{id_podcast2}/cover",
            "name": "Coding for fun",
            "summary": "summary",
            "description": "buenisimo",
            "category": None,
        }
    ]
    assert response.get_json() == expected_response

    response = client.get(f"/episodes/{id_episode}/audio")
    assert response.status_code == 404
    expected_response = {"success": False, "error": "Episode not found"}
    assert response.get_json() == expected_response

    # Delete podcast that does not exist
    response = client.delete(f"/podcasts/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

    # Delete podcast from another user
    response = client.delete(f"/podcasts/{id_podcast3}")
    assert response.status_code == 404
