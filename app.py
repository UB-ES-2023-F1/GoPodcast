import io
import os
import re
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file, Response
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

from models import Episode, Podcast, User, User_episode, db


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

    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            res = Response()
            res.headers['X-Content-Type-Options'] = '*'
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
                    }
                    for podcast in podcasts
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

    @app.post("/podcasts")
    @jwt_required()
    def post_podcast():
        current_user_id = get_jwt_identity()

        cover = request.files.get("cover").read()
        name = request.form.get("name")
        summary = request.form.get("summary")
        description = request.form.get("description")

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

    return app


if __name__ == "__main__":
    app = create_app()
    app.run()
else:
    app = create_app()
    app.run()
