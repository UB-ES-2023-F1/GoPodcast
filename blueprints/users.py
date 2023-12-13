import re
import io

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    unset_jwt_cookies,
)
from Levenshtein import distance as levenshtein_distance
from unidecode import unidecode

from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from constants.constants import CATEGORIES
from models import Follow, Notification, Podcast, User, db

users_bp = Blueprint("users_bp", __name__)


@users_bp.post("/user")
def create_user():
    username = request.form.get("username")
    image = request.files.get("image").read()
    email = request.form.get("email")
    password = request.form.get("password")

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
        username=username,
        image=image,
        email=email,
        password=generate_password_hash(password)
    )
    db.session.add(new_user)
    db.session.commit()

    return (
        jsonify({"mensaje": "Usuario " + username + " registrado correctamente"}),
        201,
    )


@users_bp.post("/login")
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
    resp = jsonify({"success": True, "access_token": access_token})
    set_access_cookies(resp, access_token)
    return resp, 200


@users_bp.post("/logout")
def logout():
    response = jsonify({"success": True})
    unset_jwt_cookies(response)
    return response


@users_bp.get("/protected")
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify(logged_in_as=current_user), 200


@users_bp.get("/search/user/<username>")
def search_user(username):
    # username attribute is unique, so there can only be 1 or 0 matches
    user = db.session.query(User).filter_by(username=username).first()

    if user:  # perfect match
        return (
            jsonify(
                [
                    {
                        "id": user.id,
                        "image_url": f"/users/{user.id}/image",
                        "username": user.username,
                        "email": user.email,
                        "verified": user.verified,
                        "match_percentage": 100,
                    }
                ]
            ),
            201,
        )

    else:  # look for partial match
        plain_username = unidecode(username).lower() # we do not consider uppercase and accents

        # get all the names of the database
        names_query = db.session.query(User.username).all()
        names = [n[0] for n in names_query]

        # compute Levenshtein distance of all of them, keep values above a threshold
        thr = 0.45

        names_above_thr = {}  # dict with (key,value)=(name,distance)
        for name in names:
            plain_name = unidecode(name).lower() # we do not consider uppercase and accents
            # just consider matches with normalized distance above a threshold
            d = levenshtein_distance(plain_name, plain_username) / max(
                len(plain_name), len(plain_username)
            )
            if d <= thr:
                names_above_thr[name] = d

        if not names_above_thr:
            return jsonify({"message": "No good matches found"}), 404

        # return best matches above the threshold
        usernames = (
            db.session.query(User).filter(User.username.in_(names_above_thr)).all()
        )

        user_list = [
                    {
                        "id": user.id,
                        "image_url": f"/users/{user.id}/image",
                        "username": user.username,
                        "email": user.email,
                        "verified": user.verified,
                        "match_percentage": round(
                            float((1 - names_above_thr[user.username]) * 100), 2
                        ),
                    }
                    for user in usernames
                ]

        sorted_user_list = sorted(user_list, key=lambda x: x["match_percentage"], reverse=True)

        return jsonify(sorted_user_list), 200


@users_bp.get("/user/<user_id>")
def get_user(user_id):
    user = db.session.query(User).filter_by(id=user_id).first()

    # check if user has at least one podcast created
    podcasts = db.session.query(Podcast).filter_by(id_author=user_id).first()
    user_type = "user"
    if podcasts:
        user_type = "author"

    return (
        jsonify(
            {
                "name": user.username,
                "image_url": f"/users/{user.id}/image",
                "bio": user.bio,
                "type": user_type,
            }
        ),
        201,
    )

@users_bp.get("/users/<id_user>/image")
def get_podcast_cover(id_user):
    user = db.session.scalars(
        select(User).where(User.id == id_user)
    ).first()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404
    return send_file(io.BytesIO(user.image), mimetype="image/jpeg")

@users_bp.put("/user/bio")
@jwt_required()
def edit_bio():
    user_id = get_jwt_identity()
    user = db.session.query(User).filter_by(id=user_id).first()

    new_bio = request.form.get("bio")
    user.bio = new_bio
    db.session.commit()
    return jsonify({"message": "Bio updated successfully"}), 201


@users_bp.get("/follows")
@jwt_required()
def get_follows():
    user_id = get_jwt_identity()
    follows = db.session.scalars(
        select(Follow).filter_by(id_follower=user_id).join(Follow.followed)
    ).all()
    return (
        jsonify(
            [{"id": f.id_followed, "username": f.followed.username} for f in follows]
        ),
        200,
    )


@users_bp.post("/follows")
@jwt_required()
def post_follows():
    current_user_id = get_jwt_identity()
    data = request.get_json()
    id = data.get("id")
    if not id:
        return jsonify({"message": "Specify the user id"}), 400
    user = db.session.scalars(select(User).where(User.id == id)).first()
    if not user:
        return jsonify({"message": "User not found"}), 404
    follow = db.session.scalars(
        select(Follow).where(
            Follow.id_follower == current_user_id, Follow.id_followed == id
        )
    ).first()
    if follow:
        return jsonify({"error": "User already followed"}), 400
    new_follow = Follow(id_follower=current_user_id, id_followed=id)
    db.session.add(new_follow)
    db.session.commit()
    return jsonify({"success": True}), 201


@users_bp.delete("/follows/<id>")
@jwt_required()
def delete_follows(id):
    current_user_id = get_jwt_identity()
    follow = db.session.scalars(
        select(Follow).where(
            Follow.id_follower == current_user_id, Follow.id_followed == id
        )
    ).first()
    if not follow:
        return jsonify({"error": "User not followed"}), 400
    db.session.delete(follow)
    db.session.commit()
    return jsonify({"success": True}), 200


@users_bp.get("/notifications")
@jwt_required()
def get_notifications():
    current_user_id = get_jwt_identity()
    notifications = db.session.scalars(
        select(Notification)
        .where(Notification.id_user == current_user_id)
        .order_by(Notification.created_at.desc())
    ).all()
    return jsonify(
        [
            {
                "id": notification.id,
                "type": notification.type,
                "object": notification.object,
                "created_at": notification.created_at,
            }
            for notification in notifications
        ]
    )


@users_bp.delete("/notifications")
@jwt_required()
def delete_notifications():
    current_user_id = get_jwt_identity()
    db.session.query(Notification).filter_by(id_user=current_user_id).delete()
    db.session.commit()
    return jsonify({"success": True}), 200
