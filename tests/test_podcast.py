import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from models import Episode, Podcast, User, User_episode, db


@pytest.fixture
def app():
    app = create_app(testing=True)
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.drop_all()


def test_post_podcast(app):
    with app.app_context():
        user = User(
            email="carlo@gmail.com",
            username="Carl Sagan",
            password=generate_password_hash("Test1234"),
            verified=True,
        )
        db.session.add(user)
        db.session.commit()

    client = app.test_client()

    data = {
        "name": "Nice podcast",
        "description": "Very nice podcast!",
        "summary": "breve resumen aquí",
        "cover": (b"", "test.jpg", "image/jpeg"),
    }

    # Unauthenticated
    response = client.post("/podcasts", data=data)
    assert response.status_code == 401

    # Authenticated
    response = client.post(
        "/login", json={"email": "carlo@gmail.com", "password": "Test1234"}
    )
    assert response.status_code == 200

    response = client.post("/podcasts", data=data)
    assert response.status_code == 201

    # Podcast with repeated combination of name and id_author
    data2 = {
        "name": "Nice podcast",
        "description": "Another very good podcast!",
        "summary": "otro breve resumen",
        "cover": (b"", "test.jpg", "image/jpeg"),
    }

    response = client.post("/podcasts", data=data2)
    assert response.status_code == 400
    expected_response = {
        "mensaje": f"This user already has a podcast with the name: {data['name']}"
    }
    assert response.get_json() == expected_response

    # Podcast with no given name
    data3 = {
        "name": "",
        "description": "Another very good podcast!",
        "summary": "otro breve resumen",
        "cover": (b"", "test.jpg", "image/jpeg"),
    }

    response = client.post("/podcasts", data=data3)
    assert response.status_code == 400
    expected_response = {"mensaje": "name field is mandatory"}
    assert response.get_json() == expected_response


def test_post_episode(app):
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
        id_podcast = podcast.id
    data = {
        "title": "title",
        "description": "description",
        "audio": (b"", "test.mp3", "audio/mpeg"),
    }
    client = app.test_client()

    # Unauthenticated
    response = client.post(f"/podcasts/{id_podcast}/episodes", data=data)
    assert response.status_code == 401

    # Authenticated
    response = client.post(
        "/login", json={"email": "test@example.com", "password": "Test1234"}
    )
    assert response.status_code == 200
    response = client.post(f"/podcasts/{id_podcast}/episodes", data=data)
    assert response.status_code == 201

    # Episode with repeated combination of title and id_podcast
    data2 = {
        "title": "title",
        "description": "description 2",
        "audio": (b"", "test.mp3", "audio/mpeg"),
    }

    response = client.post(f"/podcasts/{id_podcast}/episodes", data=data2)
    assert response.status_code == 400
    expected_response = {
        "mensaje": f"This podcast already has an episode with the title: {data2['title']}"
    }
    assert response.get_json() == expected_response

    # Podcast with no given name
    data3 = {
        "title": "",
        "description": "description 3",
        "audio": (b"", "test.mp3", "audio/mpeg"),
    }

    response = client.post(f"/podcasts/{id_podcast}/episodes", data=data3)
    assert response.status_code == 400
    expected_response = {"mensaje": "title field is mandatory"}
    assert response.get_json() == expected_response


def test_current_sec(app):
    with app.app_context():
        user = User(
            email="carlo@gmail.com",
            username="Carl Sagan",
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
        episode = Episode(
            audio=b"",
            title="How I met",
            description="how I met your mother",
            id_podcast=podcast.id,
        )
        db.session.add(episode)
        db.session.commit()
        id_episode = episode.id

    client = app.test_client()

    # Authenticated
    response = client.post(
        "/login", json={"email": "carlo@gmail.com", "password": "Test1234"}
    )
    assert response.status_code == 200

    # Episode with no previous playback
    response = client.get(f"/get_current_sec/{id_episode}")
    assert response.status_code == 201
    expected_response = {"minute": 0}
    assert response.get_json() == expected_response

    # create new current minute for that episode
    data = {"current_sec": 33}
    response = client.put(f"/update_current_sec/{id_episode}", data=data)
    assert response.status_code == 201
    expected_response = {"message": "Current minute saved for new episode played"}
    assert response.get_json() == expected_response

    # check if the minute was created successfully
    response = client.get(f"/get_current_sec/{id_episode}")
    assert response.status_code == 201
    expected_response = {"minute": 33}
    assert response.get_json() == expected_response

    # update minute of a previously played episode
    data = {"current_sec": 66}
    response = client.put(f"/update_current_sec/{id_episode}", data=data)
    assert response.status_code == 201
    expected_response = {"message": "Current minute updated successfully"}
    assert response.get_json() == expected_response

    # check if the minute was updated successfully
    response = client.get(f"/get_current_sec/{id_episode}")
    assert response.status_code == 201
    expected_response = {"minute": 66}
    assert response.get_json() == expected_response
    

def test_get_podcasts(app):
    client = app.test_client()

    # No podcasts
    response = client.get("/podcasts")
    assert response.status_code == 200
    assert response.get_json() == []

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
        id_podcast = podcast.id
        id_user = user.id

    # With podcasts
    expected_response = [
        {
            "cover": f"/podcasts/{id_podcast}/cover",
            "description": "description",
            "id": str(id_podcast),
            "id_author": str(id_user),
            "name": "podcast",
            "summary": "summary",
            "author": {
                "id": str(id_user),
                "username": "test",
            },
        }
    ]
    response = client.get("/podcasts")
    assert response.status_code == 200
    assert response.get_json() == expected_response

    # Cover
    response = client.get(f"/podcasts/{id_podcast}/cover")
    assert response.status_code == 200
    assert response.data == b""

def test_get_episodes(app):
    with app.app_context():
        user = User(
            email="test@example.com",
            username="test",
            password=generate_password_hash("Test1234"),
            verified=True,
        )
        db.session.add(user)
        db.session.commit()
        id_user = user.id
        podcast = Podcast(
            cover=b"",
            name="podcast",
            summary="summary",
            description="description",
            id_author=user.id,
          
        )
        db.session.add(podcast)
        db.session.commit()
        id_podcast = podcast.id
        episode = Episode(
            audio=b"\x48\x65",
            title="Episode1",
            description="how I met your mother",
            id_podcast=podcast.id
        )
        db.session.add(episode)
        db.session.commit()
        id_episode1 = episode.id
        episode = Episode(
            audio=b"",
            title="Episode2",
            description="how I met your mother 2",
            id_podcast=podcast.id
        )
        db.session.add(episode)
        db.session.commit()
        id_episode2 = episode.id

    client = app.test_client()

    # With podcasts
    expected_response = [
        {
            "id": str(id_episode1),
            "description": "how I met your mother",
            "title": "Episode1",
            "audio": f"/episodes/{id_episode1}/audio"
        },
        {
            "id": str(id_episode2),
            "description": "how I met your mother 2",
            "title": "Episode2",
            "audio": f"/episodes/{id_episode2}/audio"
        }
    ]
    response = client.get(f"/podcasts/{id_podcast}/episodes")
    assert response.status_code == 200
    assert response.get_json() == expected_response

    # Audio
    response = client.get(f"/episodes/{id_episode1}/audio")
    assert response.status_code == 200
    assert response.data == b"\x48\x65"

def test_get_podcast_and_populars(app):
    with app.app_context():
        user = User(
            email="carlos@gmail.com",
            username="Carl Sagan",
            password=generate_password_hash("Test1234"),
            verified=True
        )
        db.session.add(user)
        db.session.commit()
        id_user_1 = user.id
        user = User(
            email="carla@gmail.com",
            username="Carla",
            password=generate_password_hash("123456"),
            verified=True
        )
        db.session.add(user)
        db.session.commit()
        id_user_2 = user.id
        podcast = Podcast(
            cover=b"",
            name="podcast bueno",
            summary="summary",
            description="buenisimo",
            id_author=id_user_1
          
        )
        db.session.add(podcast)
        db.session.commit()
        id_podcast = podcast.id
        episode = Episode(
            audio=b"",
            title="Episode1",
            description="how I met your mother",
            id_podcast=podcast.id
        )
        db.session.add(episode)
        db.session.commit()
        id_episode_1 = episode.id
        episode = Episode(
            audio=b"",
            title="Episode2",
            description="how I met your mother",
            id_podcast=podcast.id
        )
        db.session.add(episode)
        db.session.commit()
        id_episode_2 = episode.id
        podcast = Podcast(
            cover=b"",
            name="podcast2",
            summary="summary",
            description="description",
            id_author=id_user_1
        )
        db.session.add(podcast)
        db.session.commit()
        episode = Episode(
            audio=b"",
            title="episode_pod2",
            description="how I met your mother",
            id_podcast=podcast.id
        )
        db.session.add(episode)
        db.session.commit()
        podcast = Podcast(
            cover=b"",
            name="podcast3",
            summary="summary",
            description="description",
            id_author=id_user_1
        )
        db.session.add(podcast)
        db.session.commit()
        id_podcast3 = podcast.id
        episode = Episode(
            audio=b"",
            title="Episode_pod3",
            description="how I met your mother",
            id_podcast=podcast.id
        )
        db.session.add(episode)
        db.session.commit()
        id_episode_3 = episode.id
        # create the views
        user1_episode1 = User_episode(
            id_episode = id_episode_1,
            id_user = id_user_1,
            current_sec = 20
        )
        db.session.add(user1_episode1)
        db.session.commit()
        # create the views
        user1_episode2 = User_episode(
            id_episode = id_episode_2,
            id_user = id_user_1,
            current_sec = 20
        )
        db.session.add(user1_episode2)
        db.session.commit()
        # create the views
        user2_episode3 = User_episode(
            id_episode = id_episode_3,
            id_user = id_user_2,
            current_sec = 20
        )
        db.session.add(user2_episode3)
        db.session.commit()

    client = app.test_client()

    # Retrieve a single podcast based on its id.
    response = client.get(f"/podcasts/{id_podcast}")
    assert response.status_code == 201
    expected_response = {
                            "id": str(id_podcast),
                            "id_author": str(id_user_1),
                            "author": {
                                "id": str(id_user_1),
                                "username": "Carl Sagan",
                            },
                            "cover" : f"/podcasts/{id_podcast}/cover",
                            "name" : "podcast bueno",
                            "summary" : "summary",
                            "description" : "buenisimo"
                        }
    assert response.get_json() == expected_response

    # Retrieve all the popular podcasts.
    # si no tiene views, no aparece en populares
    response = client.get("/populars")
    assert response.status_code == 201
    expected_response =[{
                            "id": str(id_podcast),
                            "id_author": str(id_user_1),
                            "author": {
                                "id": str(id_user_1),
                                "username": "Carl Sagan",
                            },
                            "cover" : f"/podcasts/{id_podcast}/cover",
                            "name" : "podcast bueno",
                            "summary" : "summary",
                            "description" : "buenisimo",
                            "views": 2   
                        },
                        {
                            "id": str(id_podcast3),
                            "id_author": str(id_user_1),
                            "author": {
                                "id": str(id_user_1),
                                "username": "Carl Sagan",
                            },
                            "cover" : f"/podcasts/{id_podcast3}/cover",
                            "name" : "podcast3",
                            "summary" : "summary",
                            "description" : "description",
                            "views": 1   
                        }]
    assert response.get_json() == expected_response
    
    