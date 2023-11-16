import io
import os
import re
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_file
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    unset_jwt_cookies,
)
from sqlalchemy import select, func
from werkzeug.security import check_password_hash, generate_password_hash
from constants import CATEGORIES

from models import Episode, Podcast, StreamLater, User, User_episode, db


def create_app(testing=False):
    app = Flask(__name__)
    load_dotenv(dotenv_path=".env")

    if testing:
        app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("POSTGRES_TEST_URL")
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("POSTGRES_URL")
    db.init_app(app)
    app.config["JWT_TOKEN_LOCATION"] = ["cookies", "headers"]
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
    CORS(
        app,
        origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            os.getenv("FRONTEND_URL"),
        ],
        supports_credentials=True,
    )
    JWTManager(app)
    with app.app_context():
        db.create_all()

    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            res = Response()
            res.headers["X-Content-Type-Options"] = "*"
            return res

    @app.after_request
    def refresh_expiring_jwts(response):
        try:
            exp_timestamp = get_jwt()["exp"]
            now = datetime.now(timezone.utc)
            target_timestamp = datetime.timestamp(now + timedelta(minutes=30))
            if target_timestamp > exp_timestamp:
                access_token = create_access_token(identity=get_jwt_identity())
                set_access_cookies(response, access_token)
            return response
        except (RuntimeError, KeyError):
            return response

    @app.route("/")
    def hello_world():  # put application's code here
        return "Hello World!"

    @app.post("/user")
    def create_user():
        data_dict = request.get_json()

        username = data_dict["username"]
        email = data_dict["email"]
        password = data_dict["password"]

        if not username or not email:
            return (
                jsonify({"mensaje": "Se requiere introducir usuario y contraseña"}),
                400,
            )

        # check if email is valid
        email_pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(email_pattern, email):
            return jsonify({"mensaje": "Dirección email no válida"}), 400

        # check if password is valid
        password_pattern = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{6,}$"
        if not re.match(password_pattern, password):
            return (
                jsonify(
                    {
                        "mensaje": "Contraseña no válida. La contraseña debe tener "
                        "como mínimo 6 caracteres, entre los cuales debe "
                        "haber almenos una letra, un número y una mayúscula"
                    }
                ),
                400,
            )

        # Check if the user with the same username or email already exists
        existing_user = db.session.query(User).filter_by(username=username).first()
        if existing_user:
            return jsonify({"mensaje": "Nombre de usuario ya existente"}), 400

        existing_email = db.session.query(User).filter_by(email=email).first()
        if existing_email:
            return jsonify({"mensaje": "Dirección email ya existente"}), 400

        # Create a new user
        new_user = User(
            username=username, email=email, password=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()

        return (
            jsonify({"mensaje": "Usuario " + username + " registrado correctamente"}),
            201,
        )

    @app.post("/login")
    def login_user():
        data = request.get_json()
        email = data["email"]
        password = data["password"]

        user = db.session.query(User).filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            return (
                jsonify({"success": False, "error": "Login details are incorrect"}),
                401,
            )
        access_token = create_access_token(identity=user.id)
        resp = jsonify({"success": True})
        set_access_cookies(resp, access_token)
        return resp, 200

    @app.post("/logout")
    def logout():
        response = jsonify({"success": True})
        unset_jwt_cookies(response)
        return response

    @app.get("/protected")
    @jwt_required()
    def protected():
        current_user = get_jwt_identity()
        return jsonify(logged_in_as=current_user), 200

    @app.get("/podcasts")
    def get_podcasts():
        limit = request.args.get("limit", default=10, type=int)
        offset = request.args.get("offset", default=0, type=int)
        podcasts = db.session.scalars(
            select(Podcast).join(Podcast.author).limit(limit).offset(offset)
        ).all()
        return (
            jsonify(
                [
                    {
                        "id": podcast.id,
                        "description": podcast.description,
                        "name": podcast.name,
                        "summary": podcast.summary,
                        "cover": f"/podcasts/{podcast.id}/cover",
                        "id_author": podcast.id_author,
                        "author": {
                            "id": podcast.author.id,
                            "username": podcast.author.username,
                        },
                        "category": podcast.category
                    }
                    for podcast in podcasts
                ]
            ),
            200,
        )
    
    @app.get("/podcasts/<id_podcast>/episodes")
    def get_episodes(id_podcast):
        episodes = db.session.scalars(
            select(Episode).where(Episode.id_podcast == id_podcast)
        ).all()       
        return (
            jsonify(
                [
                    {
                        "id": episode.id,
                        "description": episode.description,
                        "title": episode.title,
                        "audio": f"/episodes/{episode.id}/audio",
                    }
                    for episode in episodes
                ]
            ),
            200,
        )

    @app.get("/podcasts/<id_podcast>/cover")
    def get_podcast_cover(id_podcast):
        podcast = db.session.scalars(
            select(Podcast).where(Podcast.id == id_podcast)
        ).first()
        if not podcast:
            return jsonify({"success": False, "error": "Podcast not found"}), 404
        return send_file(io.BytesIO(podcast.cover), mimetype="image/jpeg")
    
    @app.get("/episodes/<id_episode>/audio")
    def get_episode_audio(id_episode):
        episode = db.session.scalars(
            select(Episode).where(Episode.id == id_episode)
        ).first()
        if not episode:
            return jsonify({"success": False, "error": "Episode not found"}), 404
        return send_file(io.BytesIO(episode.audio), mimetype="audio/mp3")

    @app.post("/podcasts")
    @jwt_required()
    def post_podcast():
        current_user_id = get_jwt_identity()

        cover = request.files.get("cover").read()
        name = request.form.get("name")
        summary = request.form.get("summary")
        description = request.form.get("description")
        category = request.form.get("category")

        if category != None and category not in CATEGORIES:
            return jsonify({"message": "Category not allowed"}),401

        if name == "":
            return jsonify({"mensaje": "name field is mandatory"}), 400

        filtered_podcast = (
            db.session.query(Podcast)
            .filter_by(id_author=current_user_id, name=name)
            .first()
        )

        if filtered_podcast is not None:
            return (
                jsonify(
                    {
                        "mensaje": f"This user already has a podcast with the name: {name}"
                    }
                ),
                400,
            )

        podcast = Podcast(
            cover=cover,
            name=name,
            summary=summary,
            description=description,
            id_author=current_user_id,
            category=category 
        )
        db.session.add(podcast)
        db.session.commit()

        return jsonify(success=True, id=podcast.id), 201

    @app.post("/podcasts/<id_podcast>/episodes")
    @jwt_required()
    def post_episode(id_podcast):
        podcast = db.session.scalars(
            select(Podcast.id).where(Podcast.id == id_podcast)
        ).first()
        if not podcast:
            return jsonify({"success": False, "error": "Podcast not found"}), 404

        audio = request.files.get("audio").read()
        title = request.form.get("title")
        description = request.form.get("description")

        if title == "":
            return jsonify({"mensaje": "title field is mandatory"}), 400

        filtered_episode = (
            db.session.query(Episode)
            .filter_by(id_podcast=id_podcast, title=title)
            .first()
        )

        if filtered_episode is not None:
            return (
                jsonify(
                    {
                        "mensaje": f"This podcast already has an episode with the title: {title}"
                    }
                ),
                400,
            )

        episode = Episode(
            audio=audio, title=title, description=description, id_podcast=id_podcast
        )
        db.session.add(episode)
        db.session.commit()

        return jsonify(success=True, id=episode.id), 201

    @app.put("/update_current_sec/<id_episode>")
    @jwt_required()
    def update_current_sec(id_episode):
        current_user_id = get_jwt_identity()

        new_current_sec = request.form.get("current_sec")

        if new_current_sec is not None:
            episode = db.session.scalars(
                select(Episode.id).where(Episode.id == id_episode)
            ).first()
            if not episode:
                return jsonify({"error": "Episode not found"}), 404

            user_episode = (
                db.session.query(User_episode)
                .filter_by(id_episode=id_episode, id_user=current_user_id)
                .first()
            )

            if user_episode:
                user_episode.current_sec = new_current_sec
                db.session.commit()
                return jsonify({"message": "Current minute updated successfully"}), 201
            else:  # first time user plays the episode
                new_user_episode = User_episode(
                    id_episode=id_episode,
                    id_user=current_user_id,
                    current_sec=new_current_sec,
                )
                db.session.add(new_user_episode)
                db.session.commit()
                return (
                    jsonify({"message": "Current minute saved for new episode played"}),
                    201,
                )

        else:
            return jsonify({"error": "Specify the current minute"}), 400

    @app.get("/get_current_sec/<id_episode>")
    @jwt_required()
    def get_current_sec(id_episode):
        current_user_id = get_jwt_identity()

        episode = db.session.scalars(
            select(Episode.id).where(Episode.id == id_episode)
        ).first()
        if not episode:
            return jsonify({"error": "Episode not found"}), 404

        user_episode = (
            db.session.query(User_episode)
            .filter_by(id_episode=id_episode, id_user=current_user_id)
            .first()
        )

        if user_episode:
            return jsonify({"minute": user_episode.current_sec}), 201
        else:  # first time user plays the episode
            return jsonify({"minute": 0}), 201

    @app.get("/stream_later")
    @jwt_required()
    def get_stream_later():
        current_user_id = get_jwt_identity()
        stream_later = db.session.scalars(
            select(StreamLater)
            .filter_by(id_user=current_user_id)
            .join(StreamLater.episode)
        ).all()
        return (
            jsonify(
                [
                    {
                        "id": entry.episode.id,
                        "title": entry.episode.title,
                        "description": entry.episode.description,
                        "id_podcast": entry.episode.id_podcast,
                    }
                    for entry in stream_later
                ]
            ),
            200,
        )

    @app.post("/stream_later")
    @jwt_required()
    def post_stream_later():
        current_user_id = get_jwt_identity()
        data = request.get_json()
        id = data.get("id")
        if not id:
            return jsonify({"error": "Specify the episode id"}), 400
        episode = db.session.scalars(select(Episode.id).where(Episode.id == id)).first()
        if not episode:
            return jsonify({"error": "Episode not found"}), 404
        entry = db.session.scalars(
            select(StreamLater).where(
                StreamLater.id_episode == id, StreamLater.id_user == current_user_id
            )
        ).first()
        if entry:
            return (
                jsonify({"error": "This episode is already in the stream later list"}),
                400,
            )
        stream_later = StreamLater(
            id_episode=id,
            id_user=current_user_id,
        )
        db.session.add(stream_later)
        db.session.commit()
        return jsonify({"success": True}), 201

    @app.delete("/stream_later/<id>")
    @jwt_required()
    def delete_stream_later(id):
        current_user_id = get_jwt_identity()
        entry = db.session.scalars(
            select(StreamLater).where(
                StreamLater.id_episode == id, StreamLater.id_user == current_user_id
            )
        ).first()
        if not entry:
            return (
                jsonify({"error": "This episode is not in the stream later list"}),
                404,
            )
        db.session.delete(entry)
        db.session.commit()
        return jsonify({"success": True}), 200

    @app.get('/podcasts/<id_podcast>')
    def get_podcast(id_podcast):
        podcast = db.session.query(Podcast).filter_by(id=id_podcast).first()

        if not podcast:
            return jsonify({"error": "Podcast not found"}), 404
        else:
            return jsonify({
                                "id": podcast.id,
                                "description": podcast.description,
                                "name": podcast.name,
                                "summary": podcast.summary,
                                "cover": f"/podcasts/{podcast.id}/cover",
                                "id_author": podcast.id_author,
                                "author": {
                                    "id": podcast.id_author,
                                    "username": podcast.author.username,
                                },
                                "category": podcast.category
                            }), 201

    @app.get('/populars')
    def get_populars():
        podcast = Podcast.__table__
        episode = Episode.__table__
        user = User.__table__
        user_episode = User_episode.__table__

        # subquery for views
        subquery = select(podcast.c.id.label('id_view'), func.count("*").label('views'))\
                    .select_from(podcast)\
                    .join(episode, podcast.c.id == episode.c.id_podcast)\
                    .join(user_episode, episode.c.id == user_episode.c.id_episode)\
                    .group_by(podcast.c.id).alias('subquery')

        # main query
        stmt = select(podcast.c.id,
                        podcast.c.cover,
                        podcast.c.name,
                        podcast.c.summary,
                        podcast.c.description,
                        podcast.c.id_author,
                        podcast.c.category,
                        user.c.username,
                        subquery.c.views)\
                .select_from(podcast)\
                .join(user, podcast.c.id_author == user.c.id)\
                .join(subquery, podcast.c.id == subquery.c.id_view)\
                .where(subquery.c.views > 0)\
                .order_by(subquery.c.views.desc())\
                .limit(10)
              
        # Execute the query
        results = db.session.execute(stmt)
        # Fetch and process the result
        data = []
        for result in results:
            data.append({
                            "id": str(result.id),
                            "description": result.description,
                            "name": result.name,
                            "summary": result.summary,
                            "cover": f"/podcasts/{result.id}/cover",
                            "id_author": result.id_author,
                            "author": {
                                "id": result.id_author,
                                "username": result.username,
                            },
                            "category": result.category,
                            "views": result.views
                        })       
        return jsonify(data), 201  
    
    @app.get('/categories')
    def get_categories():
        return jsonify({'categories': CATEGORIES}), 201
    
    @app.get('/podcasts/categories/<category>')
    def get_podcasts_of_category(category):

        if category not in CATEGORIES:
            return jsonify({"error": "Category not allowed"}),401
        
        podcasts = db.session.scalars(
            select(Podcast).where(Podcast.category == category)
            .join(User, Podcast.id_author == User.id)
        ).all()

        return (
            jsonify(
                [
                    {
                        "id": podcast.id,
                        "id_author": podcast.id_author,
                        "author": {
                            "id": podcast.id_author,
                            "username": podcast.username,
                        },
                        "cover" : podcast.cover,
                        "name" : podcast.name,
                        "summary" : podcast.summary,
                        "description" : podcast.description,
                        "category": podcast.category
                    }
                    for podcast in podcasts
                ]
            ),
            200,
        )
        

        
    return app


if __name__ == "__main__":
    app = create_app()
    app.run()
