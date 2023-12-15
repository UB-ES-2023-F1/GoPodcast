import io

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import select
from sqlalchemy.orm import contains_eager, load_only

from models import Comment, Episode, Podcast, Reply, StreamLater, User, User_episode, db
from utils.notifications import notify_new_episode

episodes_bp = Blueprint("episodes_bp", __name__)


@episodes_bp.get("/episodes/<id_episode>")
def get_episode(id_episode):
    episode = db.session.scalars(
        select(Episode).where(Episode.id == id_episode)
    ).first()
    if not episode:
        return jsonify({"success": False, "error": "Episode not found"}), 404
    podcast = db.session.scalars(
        select(Podcast).where(Podcast.id == episode.id_podcast)
    ).first()
    comments = (
        db.session.scalars(
            select(Comment)
            .where(Comment.id_episode == id_episode)
            .order_by(Comment.created_at)
            .join(Comment.user)
            .outerjoin(Comment.replies)
        )
        .unique()
        .all()
    )
    user = db.session.scalars(select(User).where(User.id == podcast.id_author)).first()
    return (
        jsonify(
            {
                "id": episode.id,
                "description": episode.description,
                "title": episode.title,
                "audio": f"/episodes/{episode.id}/audio",
                "id_podcast": episode.id_podcast,
                "podcast_name": podcast.name,
                "id_author": podcast.id_author,
                "author_name": user.username,
                "tags": episode.get_tags(),
                "comments": [
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
                        "replies": [
                            {
                                "id": reply.id,
                                "id_user": reply.id_user,
                                "id_comment": reply.id_comment,
                                "content": reply.content,
                                "created_at": reply.created_at,
                                "user": {
                                    "id": reply.user.id,
                                    "username": reply.user.username,
                                },
                            }
                            for reply in comment.replies
                        ],
                    }
                    for comment in comments
                ],
            }
        ),
        200,
    )


@episodes_bp.get("/episodes/<id_episode>/comments/<id_comment>/replies")
def get_replies_of_comment(id_episode, id_comment):
    episode = db.session.scalars(
        select(Episode).where(Episode.id == id_episode)
    ).first()
    if not episode:
        return jsonify({"success": False, "error": "Episode not found"}), 404
    comment = db.session.scalars(
        select(Comment).where(Comment.id == id_comment)
    ).first()
    if not comment:
        return jsonify({"success": False, "error": "Comment not found"}), 404
    return (
        jsonify(
            [
                {
                    "id": reply.id,
                    "id_user": reply.id_user,
                    "id_comment": reply.id_comment,
                    "content": reply.content,
                    "created_at": reply.created_at,
                    "user": {
                        "id": reply.user.id,
                        "username": reply.user.username,
                    },
                }
                for reply in comment.replies
            ]
        ),
        200,
    )


@episodes_bp.get("/podcasts/<id_podcast>/episodes")
def get_episodes_of_podcast(id_podcast):
    episodes = db.session.scalars(
        select(Episode)
        .options(
            load_only(
                Episode.id,
                Episode.title,
                Episode.description,
                Episode.id_podcast,
                Episode.tags,
            )
        )
        .where(Episode.id_podcast == id_podcast)
    ).all()
    return (
        jsonify(
            [
                {
                    "id": episode.id,
                    "description": episode.description,
                    "title": episode.title,
                    "tags": episode.get_tags(),
                    "audio": f"/episodes/{episode.id}/audio",
                }
                for episode in episodes
            ]
        ),
        200,
    )


@episodes_bp.get("/episodes/<id_episode>/audio")
def get_episode_audio(id_episode):
    episode = db.session.scalars(
        select(Episode).where(Episode.id == id_episode)
    ).first()
    if not episode:
        return jsonify({"success": False, "error": "Episode not found"}), 404
    return send_file(io.BytesIO(episode.audio), mimetype="audio/mp3")


@episodes_bp.get("/episodes/<id_episode>/comments")
def get_episode_comments(id_episode):
    episode = db.session.scalars(
        select(Episode).where(Episode.id == id_episode)
    ).first()
    if not episode:
        return jsonify({"success": False, "error": "Episode not found"}), 404
    comments = (
        db.session.scalars(
            select(Comment)
            .where(Comment.id_episode == id_episode)
            .order_by(Comment.created_at)
            .join(Comment.user)
            .outerjoin(Comment.replies)
        )
        .unique()
        .all()
    )
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
                    "replies": [
                        {
                            "id": reply.id,
                            "id_user": reply.id_user,
                            "id_comment": reply.id_comment,
                            "content": reply.content,
                            "created_at": reply.created_at,
                            "user": {
                                "id": reply.user.id,
                                "username": reply.user.username,
                            },
                        }
                        for reply in comment.replies
                    ],
                }
                for comment in comments
            ]
        ),
        200,
    )


@episodes_bp.post("/episodes/<id_episode>/comments")
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


@episodes_bp.post("/comments/<id_comment>/replies")
@jwt_required()
def post_comment_replies(id_comment):
    comment = db.session.scalars(
        select(Comment).where(Comment.id == id_comment)
    ).first()
    if not comment:
        return jsonify({"success": False, "error": "Comment not found"}), 404
    current_user_id = get_jwt_identity()
    data = request.get_json()
    content = data.get("content")
    if not content:
        return jsonify({"error": "Specify the content of the reply"}), 400
    reply = Reply(
        content=content,
        id_user=current_user_id,
        id_comment=id_comment,
    )
    db.session.add(reply)
    db.session.commit()
    return jsonify({"success": True}), 201


@episodes_bp.delete("/episodes/<id_episode>/comments/<id_comment>")
@episodes_bp.delete("/comments/<id_comment>")
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


@episodes_bp.delete("/replies/<id_reply>")
@jwt_required()
def delete_comment_replies(id_reply):
    reply = db.session.scalars(select(Reply).where(Reply.id == id_reply)).first()
    if not reply:
        return jsonify({"success": False, "error": "Reply not found"}), 404
    current_user_id = get_jwt_identity()
    if str(reply.id_user) != current_user_id:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "You are not the author of this reply",
                }
            ),
            403,
        )
    db.session.delete(reply)
    db.session.commit()
    return jsonify({"success": True}), 200


@episodes_bp.post("/podcasts/<id_podcast>/episodes")
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
    tags_str = request.form.get("tags")

    if title == "":
        return jsonify({"mensaje": "title field is mandatory"}), 400

    filtered_episode = (
        db.session.query(Episode).filter_by(id_podcast=id_podcast, title=title).first()
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
    if tags_str:
        tags = [tag.strip() for tag in tags_str.split("#")]
        episode.set_tags(tags)

    db.session.add(episode)
    db.session.commit()

    notify_new_episode(episode, db.session)

    return jsonify(success=True, id=episode.id), 201


@episodes_bp.put("/update_current_sec/<id_episode>")
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
        return (
            jsonify(
                {"error": "Specify the current minute", "current_sec": new_current_sec}
            ),
            400,
        )


@episodes_bp.get("/get_current_sec/<id_episode>")
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


@episodes_bp.delete("/episodes/<id_episode>")
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


@episodes_bp.put("/episodes/<id_episode>")
@jwt_required()
def edit_episode(id_episode):
    current_user_id = get_jwt_identity()

    new_audio = request.files.get("audio")
    if new_audio:
        new_audio = new_audio.read()
    new_title = request.form.get("title")
    new_description = request.form.get("description")
    new_tags = request.form.get("tags")

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

    if new_audio is not None:
        episode.audio = new_audio
    if new_description:
        episode.description = new_description
    if new_tags:
        tags = [tag.strip() for tag in new_tags.split("#")]
        episode.set_tags(tags)

    db.session.commit()
    return jsonify({"message": "Episode updated successfully"}), 201


@episodes_bp.get("/stream_later")
@jwt_required()
def get_stream_later():
    current_user_id = get_jwt_identity()
    stream_later = db.session.scalars(
        select(StreamLater).filter_by(id_user=current_user_id).join(StreamLater.episode)
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


@episodes_bp.get("/stream_later/<id_episode>")
@jwt_required()
def get_stream_later_by_id(id_episode):
    current_user_id = get_jwt_identity()
    stream_later = db.session.scalars(
        select(StreamLater)
        .filter_by(id_user=current_user_id)
        .filter_by(id_episode=id_episode)
    ).first()
    if stream_later:
        return (
            {"is_liked": True},
            200,
        )
    else:
        return (
            {"is_liked": False},
            200,
        )


@episodes_bp.post("/stream_later")
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


@episodes_bp.delete("/stream_later/<id>")
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
