"""
"""

from typing import Optional
from sqlalchemy import Table, Column, ForeignKey, Identity, Text
from sqlalchemy.orm import Mapped, relationship, mapped_column
from Nerris.database.base import Base

UserNation = Table(
    "user_nations",
    Base.metadata,
    Column("nation_id", ForeignKey("nations.id"), primary_key=True),
    Column("user_id", ForeignKey("users.id"), primary_key=True)
)

GuildRegion = Table(
    "guild_regions",
    Base.metadata,
    Column("region_id", ForeignKey("regions.id"), primary_key=True),
    Column("guild_id", ForeignKey("guilds.id"), primary_key=True)
)


RoleMeaning = Table(
    "role_meanings",
    Base.metadata,
    Column("meaning_id", ForeignKey("meanings.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True)
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    snowflake: Mapped[int]

    nations: Mapped[set["Nation"]] = relationship(secondary=UserNation, back_populates="users", cascade="save-update, merge, delete")


class Guild(Base):
    __tablename__ = "guilds"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    snowflake: Mapped[int]

    regions: Mapped[set["Region"]] = relationship(secondary=GuildRegion, back_populates="guilds", cascade="save-update, merge, delete")
    roles: Mapped[set["Role"]] = relationship(back_populates="guild", cascade="save-update, merge, delete, delete-orphan")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    snowflake: Mapped[int]

    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"))

    meanings: Mapped[set["Meaning"]] = relationship(secondary=RoleMeaning, back_populates="roles", cascade='save-update, merge, delete')
    guild: Mapped["Guild"] = relationship(back_populates="roles", cascade="save-update, merge, delete")


class Meaning(Base):
    __tablename__ = "meanings"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    meaning: Mapped[str] = mapped_column(Text)

    roles: Mapped[set["Role"]] = relationship(secondary=RoleMeaning, back_populates="meanings", cascade="save-update, merge, delete")


class Nation(Base):
    __tablename__ = "nations"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    name: Mapped[str]

    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))


    users: Mapped[set["User"]] = relationship(secondary=UserNation, back_populates="nations", cascade="save-update, merge, delete")
    region: Mapped["Region"] = relationship(back_populates="nations", cascade="save-update, merge, delete")


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    name: Mapped[str]

    nations: Mapped[set["Nation"]] = relationship(back_populates="region", cascade="save-update, merge, delete, delete-orphan")
    guilds: Mapped[set["Guild"]] = relationship(secondary=GuildRegion, back_populates="regions", cascade="save-update, merge, delete")


# class RegionalMessageBoard(Base):
#     __tablename__ = "rmb"

#     id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
#     author_id: Mapped[int] = mapped_column(ForeignKey("nations.id"))
#     region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
#     message: Mapped[str]
#     date: Mapped[int]

#     author: Mapped["Nation"] = relationship()
#     region: Mapped["Region"] = relationship()
