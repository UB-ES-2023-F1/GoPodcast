from sqlalchemy import select
from sqlalchemy.orm import scoped_session

from models import Follow, Notification, Podcast, Episode


def notify_new_podcast(podcast: Podcast, session: scoped_session):
    follows = session.scalars(
        select(Follow).where(Follow.id_followed == podcast.id_author)
    ).all()
    notifications = []
    for follow in follows:
        notifications.append(
            Notification(
                id_user=follow.id_follower,
                type="new_podcast",
                object={"id": str(podcast.id), "name": podcast.name},
            )
        )
    session.add_all(notifications)
    session.commit()


def notify_new_episode(episode: Episode, session: scoped_session):
    podcast = session.scalars(select(Podcast).where(Podcast.id == episode.id_podcast)).first()
    follows = session.scalars(
        select(Follow).where(Follow.id_followed == podcast.id_author)
    ).all()
    notifications = []
    for follow in follows:
        notifications.append(
            Notification(
                id_user=follow.id_follower,
                type="new_episode",
                object={
                    "id": str(episode.id),
                    "title": episode.title,
                    "description": episode.description,
                },
            )
        )
    session.add_all(notifications)
    session.commit()
