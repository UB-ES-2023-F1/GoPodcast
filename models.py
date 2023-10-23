import uuid

from sqlalchemy import UUID, text, Binary, ForeignKey
from sqlalchemy.orm import (DeclarativeBase, Mapped, MappedAsDataclass,
                            mapped_column)


class Base(MappedAsDataclass, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'user'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        init=False,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        unique=True,
        nullable=False,
    )
    email: Mapped[str] = mapped_column(unique=True)
    username: Mapped[str] = mapped_column(unique=True)
    password: Mapped[str]
    verified: Mapped[bool] = mapped_column(default=False)

class Podcast(Base):
    __tablename__ = 'podcast'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        init=False,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        unique=True,
        nullable=False,
    )
    cover: Mapped[Binary]
    name: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str]
    id_author: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
