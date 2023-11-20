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
from sqlalchemy import func, select
from werkzeug.security import check_password_hash, generate_password_hash

from constants.constants import CATEGORIES
from models import (
    Comment,
    Episode,
    Favorite,
    Podcast,
    StreamLater,
    User,
    User_episode,
    db,
)

from Levenshtein import distance as levenshtein_distance


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
                        "category": podcast.category,
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

    @app.get("/episodes/<id_episode>/comments")
    def get_episode_comments(id_episode):
        episode = db.session.scalars(
            select(Episode).where(Episode.id == id_episode)
        ).first()
        if not episode:
            return jsonify({"success": False, "error": "Episode not found"}), 404
        comments = db.session.scalars(
            select(Comment)
            .where(Comment.id_episode == id_episode)
            .order_by(Comment.created_at)
            .join(Comment.user)
        ).all()
        return (
            jsonify(
                [
                    {
                        "id": comment.id,
                        "id_user": comment.id_user,
                        "id_episode": comment.id_episode,
                        "content": comment.content,
                        "created_at": comment.created_at,
                        "user": {
                            "id": comment.user.id,
                            "username": comment.user.username,
                        },
                    }
                    for comment in comments
                ]
            ),
            200,
        )

    @app.post("/episodes/<id_episode>/comments")
    @jwt_required()
    def post_episode_comments(id_episode):
        episode = db.session.scalars(
            select(Episode).where(Episode.id == id_episode)
        ).first()
        if not episode:
            return jsonify({"success": False, "error": "Episode not found"}), 404
        current_user_id = get_jwt_identity()
        data = request.get_json()
        content = data.get("content")
        if not content:
            return jsonify({"error": "Specify the content of the comment"}), 400
        comment = Comment(
            content=content,
            id_user=current_user_id,
            id_episode=id_episode,
        )
        db.session.add(comment)
        db.session.commit()
        return jsonify({"success": True}), 201

    @app.delete("/episodes/<id_episode>/comments/<id_comment>")
    @app.delete("/comments/<id_comment>")
    @jwt_required()
    def delete_episode_comments(id_comment, id_episode=None):
        comment = db.session.scalars(
            select(Comment).where(Comment.id == id_comment)
        ).first()
        if not comment:
            return jsonify({"success": False, "error": "Comment not found"}), 404
        current_user_id = get_jwt_identity()
        if str(comment.id_user) != current_user_id:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "You are not the author of this comment",
                    }
                ),
                403,
            )
        db.session.delete(comment)
        db.session.commit()
        return jsonify({"success": True}), 200

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
            return jsonify({"message": "Category not allowed"}), 401

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
            category=category,
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

    @app.get("/favorites")
    @jwt_required()
    def get_favorites():
        current_user_id = get_jwt_identity()
        favorites = db.session.scalars(
            select(Favorite)
            .filter_by(id_user=current_user_id)
            .join(Favorite.podcast)
            .join(Podcast.author)
        ).all()
        return (
            jsonify(
                [
                    {
                        "id": entry.podcast.id,
                        "name": entry.podcast.name,
                        "description": entry.podcast.description,
                        "summary": entry.podcast.summary,
                        "cover": f"/podcasts/{entry.podcast.id}/cover",
                        "id_author": entry.podcast.id_author,
                        "author": {
                            "id": entry.podcast.author.id,
                            "username": entry.podcast.author.username,
                        },
                        "category": entry.podcast.category,
                    }
                    for entry in favorites
                ]
            ),
            200,
        )

    @app.post("/favorites")
    @jwt_required()
    def post_favorites():
        current_user_id = get_jwt_identity()
        data = request.get_json()
        id = data.get("id")
        if not id:
            return jsonify({"error": "Specify the podcast id"}), 400
        podcast = db.session.scalars(select(Podcast.id).where(Podcast.id == id)).first()
        if not podcast:
            return jsonify({"error": "Podcast not found"}), 404
        entry = db.session.scalars(
            select(Favorite).where(
                Favorite.id_podcast == id, Favorite.id_user == current_user_id
            )
        ).first()
        if entry:
            return (
                jsonify({"error": "This podcast is already in the favorites list"}),
                400,
            )
        favorite = Favorite(
            id_podcast=id,
            id_user=current_user_id,
        )
        db.session.add(favorite)
        db.session.commit()
        return jsonify({"success": True}), 201

    @app.delete("/favorites/<id>")
    @jwt_required()
    def delete_favorites(id):
        current_user_id = get_jwt_identity()
        entry = db.session.scalars(
            select(Favorite).where(
                Favorite.id_podcast == id, Favorite.id_user == current_user_id
            )
        ).first()
        if not entry:
            return (
                jsonify({"error": "This podcast is not in the favorites list"}),
                404,
            )
        db.session.delete(entry)
        db.session.commit()
        return jsonify({"success": True}), 200

    @app.get("/podcasts/<id_podcast>")
    def get_podcast(id_podcast):
        podcast = db.session.query(Podcast).filter_by(id=id_podcast).first()

        if not podcast:
            return jsonify({"error": "Podcast not found"}), 404
        else:
            return (
                jsonify(
                    {
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
                        "category": podcast.category,
                    }
                ),
                201,
            )

    @app.get("/populars")
    def get_populars():
        podcast = Podcast.__table__
        episode = Episode.__table__
        user = User.__table__
        user_episode = User_episode.__table__

        # subquery for views
        subquery = (
            select(podcast.c.id.label("id_view"), func.count("*").label("views"))
            .select_from(podcast)
            .join(episode, podcast.c.id == episode.c.id_podcast)
            .join(user_episode, episode.c.id == user_episode.c.id_episode)
            .group_by(podcast.c.id)
            .alias("subquery")
        )

        # main query
        stmt = (
            select(
                podcast.c.id,
                podcast.c.cover,
                podcast.c.name,
                podcast.c.summary,
                podcast.c.description,
                podcast.c.id_author,
                podcast.c.category,
                user.c.username,
                subquery.c.views,
            )
            .select_from(podcast)
            .join(user, podcast.c.id_author == user.c.id)
            .join(subquery, podcast.c.id == subquery.c.id_view)
            .where(subquery.c.views > 0)
            .order_by(subquery.c.views.desc())
            .limit(10)
        )

        # Execute the query
        results = db.session.execute(stmt)
        # Fetch and process the result
        data = []
        for result in results:
            data.append(
                {
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
                    "views": result.views,
                }
            )
        return jsonify(data), 201

    @app.get("/categories")
    def get_categories():
        c = []
        jpg_categories = ["Deportes", "Entretenimiento", "Música"]
        for category in CATEGORIES:
            if category in jpg_categories:
                ext = ".jpg"
            else:
                ext = ".png"
            c.append({
                        "image_url": f"/categories/images/{category}"+ext,
                        "title": category
                    })
            
        return jsonify(c),200
    
    @app.get("/categories/images/<filename>")
    def get_image_of_category(filename):
        return send_file(os.path.join('constants', filename))

    @app.get("/podcasts/categories/<category>")
    def get_podcasts_of_category(category):
        if category not in CATEGORIES:
            return jsonify({"error": "Category not allowed"}), 401

        podcasts = db.session.scalars(
            select(Podcast)
            .where(Podcast.category == category)
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
                        "cover": f"/podcasts/{podcast.id}/cover",
                        "name": podcast.name,
                        "summary": podcast.summary,
                        "description": podcast.description,
                        "category": podcast.category,
                    }
                    for podcast in podcasts
                ]
            ),
            200,
        )

    @app.get("/search/podcast/<podcast_name>")
    def search_podcast(podcast_name):
        # name attribute is unique, so there can only be 1 or 0 matches
        podcast = db.session.query(Podcast).filter_by(name=podcast_name).first()

        if podcast: # perfect match
            return (
                jsonify(
                    [{
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
                        "category": podcast.category,
                        "match_percentatge": 100
                    }]
                ),
                201,
            )
        
        else: # look for partial match
            # get all the names of the database
            names_query = db.session.query(Podcast.name).all()
            names = [n[0] for n in names_query]

            # compute Levenshtein distance of all of them, keep values above a threshold
            thr = 0.4
            
            names_above_thr = {} # dict with (key,value)=(name,distance)
            for name in names:
                # just consider matches with normalized distance above a threshold
                d = levenshtein_distance(name, podcast_name) / max(len(name),len(podcast_name))
                if d <= thr:
                    names_above_thr[name] = d

            if not names_above_thr:
                return jsonify({"message": "No good matches found"}), 404

            # return best matches above the threshold
            podcasts = db.session.query(Podcast).filter(Podcast.name.in_(names_above_thr)).all()
            return (
                jsonify(
                    [
                        {
                            "id": podcast.id,
                            "id_author": podcast.id_author,
                            "author": {
                                "id": podcast.id_author,
                                "username": podcast.author.username,
                            },
                            "cover": f"/podcasts/{podcast.id}/cover",
                            "name": podcast.name,
                            "summary": podcast.summary,
                            "description": podcast.description,
                            "category": podcast.category,
                            "match_percentatge": round(float((1-names_above_thr[podcast.name])*100),2)
                        }
                        for podcast in podcasts
                    ]
                ),
                200,
            )


    @app.get("/search/user/<username>")
    def search_user(username):
        # username attribute is unique, so there can only be 1 or 0 matches
        user = db.session.query(User).filter_by(username=username).first()

        if user: # perfect match
            return (
                jsonify(
                    [{
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "verified": user.verified,
                        "match_percentatge": 100
                    }]
                ),
                201,
            )
        
        else: # look for partial match
            # get all the names of the database
            names_query = db.session.query(User.username).all()
            names = [n[0] for n in names_query]

            # compute Levenshtein distance of all of them, keep values above a threshold
            thr = 0.4
            
            names_above_thr = {} # dict with (key,value)=(name,distance)
            for name in names:
                # just consider matches with normalized distance above a threshold
                d = levenshtein_distance(name, username) / max(len(name),len(username))
                if d <= thr:
                    names_above_thr[name] = d

            if not names_above_thr:
                return jsonify({"message": "No good matches found"}), 404
            
            # return best matches above the threshold
            usernames = db.session.query(User).filter(User.username.in_(names_above_thr)).all()
            return (
                jsonify(
                    [
                        {
                            "id": user.id,
                            "username": user.username,
                            "email": user.email,
                            "verified": user.verified,
                            "match_percentatge": round(float((1-names_above_thr[user.username])*100),2)
                        }
                        for user in usernames
                    ]
                ),
                200,
            )
        
    @app.get("/user/<user_id>")
    def get_user(user_id):
        user = db.session.query(User).filter_by(id=user_id).first()

        return (
                jsonify(
                    {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "verified": user.verified,
                    }
                ),
                201,
            )

    @app.get("/user/created_podcasts/<user_id>")
    def get_created_podcasts_by_user(user_id):
        # name attribute is unique, so there can only be 1 or 0 matches
        podcasts = db.session.query(Podcast).filter_by(id_author=user_id).all()

        if not podcasts:
            return jsonify({"message": "User has no podcast created"}), 201
        else:
            return (
                jsonify(
                    [
                        {
                            "id": podcast.id,
                            "author": {
                                "id": podcast.id_author,
                                "username": podcast.author.username,
                            },
                            "cover": f"/podcasts/{podcast.id}/cover",
                            "name": podcast.name,
                            "summary": podcast.summary,
                            "description": podcast.description,
                            "category": podcast.category,
                        }
                        for podcast in podcasts
                    ]
                ),
                200,
            )
        
    @app.put("/podcasts/<id_podcast>")
    @jwt_required()
    def edit_podcast(id_podcast):
        current_user_id = get_jwt_identity()

        new_cover = request.files.get("cover")
        if new_cover:
            new_cover=new_cover.read()
        new_name = request.form.get("name")
        new_summary = request.form.get("summary")
        new_description = request.form.get("description")
        new_category = request.form.get("category")

        # Let's first check the validity of the new data
        if new_category != None and new_category not in CATEGORIES:
            return jsonify({"message": "Category not allowed"}), 401
        
        podcast = db.session.scalars(
            select(Podcast).where(Podcast.id == id_podcast)
        ).first()

        if not podcast:
            return jsonify({"error": "Podcast not found"}), 404

        if str(podcast.id_author) != current_user_id:
            return jsonify({"error": "User can only edit their own creations"}), 404
        
        if new_name and new_name != "" and new_name != podcast.name:
            filtered_podcast = (
                db.session.query(Podcast)
                .filter_by(id_author=current_user_id, name=new_name)
                .first()
            )

            if filtered_podcast is not None:
                return (
                    jsonify(
                        {
                            "mensaje": f"This user already has a podcast with the name: {new_name}"
                        }
                    ),
                    400,
                )
            else:
                podcast.name = new_name

        
        if new_cover: podcast.cover = new_cover
        if new_summary: podcast.summary = new_summary
        if new_description: podcast.description = new_description
        if new_category: podcast.category = new_category

        db.session.commit()
        return jsonify({"message": "Podcast updated successfully"}), 201

        
    @app.put("/episodes/<id_episode>")
    @jwt_required()
    def edit_episode(id_episode):
        current_user_id = get_jwt_identity()

        new_audio = request.files.get("audio")
        if new_audio:
            new_audio = new_audio.read()
        new_title = request.form.get("title")
        new_description = request.form.get("description")

        episode = db.session.scalars(
            select(Episode).where(Episode.id == id_episode)
        ).first()

        if not episode:
            return jsonify({"error": "Episode not found"}), 404

        podcast = db.session.scalars(
            select(Podcast).where(Podcast.id == episode.id_podcast)
        ).first()

        if str(podcast.id_author) != current_user_id:
            return jsonify({"error": "User can only edit their own creations"}), 404
        
        if new_title and new_title != "" and new_title != episode.title:
            filtered_episode = (
                db.session.query(Episode)
                .filter_by(id_podcast=podcast.id, title=new_title)
                .first()
            )

            if filtered_episode is not None:
                return (
                    jsonify(
                        {
                        "mensaje": f"This podcast already has an episode with the title: {new_title}"
                    }
                    ),
                    400,
                )
            else:
                episode.title = new_title
        
        if new_audio: episode.audio = new_audio
        if new_description: episode.description = new_description

        db.session.commit()
        return jsonify({"message": "Episode updated successfully"}), 201

    @app.delete("/podcasts/<id_podcast>")
    @jwt_required()
    def delete_podcast(id_podcast):
        current_user_id = get_jwt_identity()

        podcast = db.session.scalars(
            select(Podcast).where(Podcast.id == id_podcast)
        ).first()

        if not podcast:
            return jsonify({"error": "Podcast not found"}), 404

        if str(podcast.id_author) != current_user_id:
            return jsonify({"error": "User can only delete their own creations"}), 404
        
        # all episodes and other dependencies will be automatically deleted
        # because we set an "on delete cascade" behaviour

        db.session.delete(podcast)
        db.session.commit()
        return jsonify({"success": True}), 200
    
    @app.delete("/episodes/<id_episode>")
    @jwt_required()
    def delete_episode(id_episode):
        current_user_id = get_jwt_identity()

        episode = db.session.scalars(
            select(Episode).where(Episode.id == id_episode)
        ).first()

        if not episode:
            return jsonify({"error": "Episode not found"}), 404

        podcast = db.session.scalars(
            select(Podcast).where(Podcast.id == episode.id_podcast)
        ).first()

        if str(podcast.id_author) != current_user_id:
            return jsonify({"error": "User can only edit their own creations"}), 404
        
        # all dependencies will be automatically deleted
        # because we set an "on delete cascade" behaviour

        db.session.delete(episode)
        db.session.commit()
        return jsonify({"success": True}), 200
    

    return app


if __name__ == "__main__":
    app = create_app()
    app.run()
else:
    app = create_app()
