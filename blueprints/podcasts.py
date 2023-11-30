import io
import os

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from Levenshtein import distance as levenshtein_distance
from unidecode import unidecode

from sqlalchemy import func, select

from constants.constants import CATEGORIES
from models import Episode, Favorite, Podcast, User, User_episode, db
from utils.notifications import notify_new_podcast

podcasts_bp = Blueprint("podcasts_bp", __name__)


@podcasts_bp.get("/podcasts")
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


@podcasts_bp.get("/podcasts/<id_podcast>")
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


@podcasts_bp.get("/user/created_podcasts/<user_id>")
def get_podcasts_created_by_user(user_id):
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


@podcasts_bp.get("/podcasts/<id_podcast>/cover")
def get_podcast_cover(id_podcast):
    podcast = db.session.scalars(
        select(Podcast).where(Podcast.id == id_podcast)
    ).first()
    if not podcast:
        return jsonify({"success": False, "error": "Podcast not found"}), 404
    return send_file(io.BytesIO(podcast.cover), mimetype="image/jpeg")


@podcasts_bp.post("/podcasts")
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
                {"mensaje": f"This user already has a podcast with the name: {name}"}
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

    notify_new_podcast(podcast, db.session)

    return jsonify(success=True, id=podcast.id), 201


@podcasts_bp.put("/podcasts/<id_podcast>")
@jwt_required()
def edit_podcast(id_podcast):
    current_user_id = get_jwt_identity()

    new_cover = request.files.get("cover")
    if new_cover:
        new_cover = new_cover.read()
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

    if new_cover:
        podcast.cover = new_cover
    if new_summary:
        podcast.summary = new_summary
    if new_description:
        podcast.description = new_description
    if new_category:
        podcast.category = new_category

    db.session.commit()
    return jsonify({"message": "Podcast updated successfully"}), 201


@podcasts_bp.delete("/podcasts/<id_podcast>")
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


@podcasts_bp.get("/search/podcast/<podcast_name>")
def search_podcast(podcast_name):
    # name attribute is unique, so there can only be 1 or 0 matches
    podcast = db.session.query(Podcast).filter_by(name=podcast_name).first()

    if podcast:  # perfect match
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
                            "id": podcast.id_author,
                            "username": podcast.author.username,
                        },
                        "category": podcast.category,
                        "match_percentatge": 100,
                    }
                ]
            ),
            201,
        )

    else:  # look for partial match
        plain_podcast_name = unidecode(podcast_name).lower() # we do not consider uppercase and accents

        # get all the names of the database
        names_query = db.session.query(Podcast.name).all()
        names = [n[0] for n in names_query]

        # compute Levenshtein distance of all of them, keep values above a threshold
        thr = 0.45

        names_above_thr = {}  # dict with (key,value)=(name,distance)
        for name in names:
            plain_name = unidecode(name).lower() # we do not consider uppercase and accents
            # just consider matches with normalized distance above a threshold
            d = levenshtein_distance(plain_name, plain_podcast_name) / max(
                len(plain_name), len(plain_podcast_name)
            )
            if d <= thr:
                names_above_thr[name] = d

        if not names_above_thr:
            return jsonify({"message": "No good matches found"}), 404

        # return best matches above the threshold
        podcasts = (
            db.session.query(Podcast).filter(Podcast.name.in_(names_above_thr)).all()
        )
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
                        "match_percentatge": round(
                            float((1 - names_above_thr[podcast.name]) * 100), 2
                        ),
                    }
                    for podcast in podcasts
                ]
            ),
            200,
        )


@podcasts_bp.get("/podcasts/categories/<category>")
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


@podcasts_bp.get("/categories/images/<filename>")
def get_image_of_category(filename):
    return send_file(os.path.join("constants", filename))


@podcasts_bp.get("/categories")
def get_categories():
    c = []
    jpg_categories = ["Deportes", "Entretenimiento", "Música"]
    for category in CATEGORIES:
        if category in jpg_categories:
            ext = ".jpg"
        else:
            ext = ".png"
        c.append(
            {"image_url": f"/categories/images/{category}" + ext, "title": category}
        )

    return jsonify(c), 200


@podcasts_bp.get("/populars")
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


@podcasts_bp.get("/favorites")
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


@podcasts_bp.post("/favorites")
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


@podcasts_bp.delete("/favorites/<id>")
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
