import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from models import Podcast, User, Episode, User_episode, db


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
            verified=True
        )
        db.session.add(user)
        db.session.commit()

    client = app.test_client()

    data = {
        "name": "Nice podcast",
        "description": "Very nice podcast!",
        "summary": "breve resumen aquí",
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

    # Podcast with repeated combination of name and id_author
    data2 = {
        "name": "Nice podcast",
        "description": "Another very good podcast!",
        "summary": "otro breve resumen",
        "cover": (b"", "test.jpg", "image/jpeg")
    }

    response = client.post("/podcasts", data=data2)
    assert response.status_code == 400
    expected_response = {
        "mensaje": f"This user already has a podcast with the name: {data['name']}"}
    assert response.get_json() == expected_response

    # Podcast with no given name
    data3 = {
        "name": "",
        "description": "Another very good podcast!",
        "summary": "otro breve resumen",
        "cover": (b"", "test.jpg", "image/jpeg")
    }

    response = client.post("/podcasts", data=data3)
    assert response.status_code == 400
    expected_response = {
        "mensaje": "name field is mandatory"}
    assert response.get_json() == expected_response


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
            summary="summary",
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

    # Episode with repeated combination of title and id_podcast
    data2 = {
        "title": "title",
        "description": "description 2",
        "audio": (b"", "test.mp3", "audio/mpeg")
    }

    response = client.post(f"/podcasts/{id_podcast}/episodes", data=data2)
    assert response.status_code == 400
    expected_response = {
        "mensaje": f"This podcast already has an episode with the title: {data2['title']}"}
    assert response.get_json() == expected_response

    # Podcast with no given name
    data3 = {
        "title": "",
        "description": "description 3",
        "audio": (b"", "test.mp3", "audio/mpeg")
    }

    response = client.post(f"/podcasts/{id_podcast}/episodes", data=data3)
    assert response.status_code == 400
    expected_response = {
        "mensaje": "title field is mandatory"}
    assert response.get_json() == expected_response

def test_current_sec(app):
    with app.app_context():
        user = User(
            email="carlo@gmail.com",
            username="Carl Sagan",
            password=generate_password_hash("Test1234"),
            verified=True
        )
        db.session.add(user)
        db.session.commit()
        podcast = Podcast(
            cover=b"",
            name="podcast",
            summary="summary",
            description="description",
            id_author=user.id
        )
        db.session.add(podcast)
        db.session.commit()
        episode = Episode(
            audio=b"",
            title="How I met",
            description="how I met your mother",
            id_podcast=podcast.id
        )
        db.session.add(episode)
        db.session.commit()
        id_episode = episode.id

    client = app.test_client()

    # Authenticated
    response = client.post('/login', json={"email": "carlo@gmail.com",
                                           "password": "Test1234"})
    assert response.status_code == 200

    # Episode with no previous playback
    response = client.get(f"/get_current_sec/{id_episode}")
    assert response.status_code == 201
    expected_response = {"minute": 0}
    assert response.get_json() == expected_response

    # create new current minute for that episode
    data = {'current_sec':33}
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
    data = {'current_sec':66}
    response = client.put(f"/update_current_sec/{id_episode}", data=data)
    assert response.status_code == 201
    expected_response = {"message": "Current minute updated successfully"}
    assert response.get_json() == expected_response

    # check if the minute was updated successfully
    response = client.get(f"/get_current_sec/{id_episode}")
    assert response.status_code == 201
    expected_response = {"minute": 66}
    assert response.get_json() == expected_response
