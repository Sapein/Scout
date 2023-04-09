"""
"""

from typing import Optional, Set
from sqlalchemy import Table, Column, ForeignKey, Identity, Text
from sqlalchemy.orm import Mapped, relationship, mapped_column
from Nerris.database.base import Base


class UserNation(Base):
    __tablename__ = "user_nations"

    nation_id: Mapped[int] = mapped_column(ForeignKey("nations.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)

class GuildRegion(Base):
    __tablename__ = "guild_regions"

    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), primary_key=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), primary_key=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    snowflake: Mapped[str]

    # nations: Mapped[Set["Nation"]] = relationship(secondary=UserNation)

class Guild(Base):
    __tablename__ = "guilds"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    snowflake: Mapped[str]

    # regions: Mapped[Set["Region"]] = relationship(secondary=GuildRegion)

class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    snowflake: Mapped[str]

    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"))


class Meaning(Base):
    __tablename__ = "meanings"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    meaning: Mapped[str] = mapped_column(Text)

class RoleMeaning(Base):
    __tablename__ = "role_meanings"

    meaning_id: Mapped[str] = mapped_column(ForeignKey("meanings.id"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), primary_key=True)


class Nation(Base):
    __tablename__ = "nations"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    name: Mapped[str]
    url_name: Mapped[str]
    region_id: Mapped[Optional[int]] = mapped_column(ForeignKey("regions.id"))


    # user: Mapped["User"] = relationship(secondary=UserNation)
    # region: Mapped["Region"] = relationship(back_populates="nations")


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    name: Mapped[str]
    url_name: Mapped[str]

    # nations: Mapped[Set["Nation"]] = relationship(back_populates="region")
    # guild: Mapped["Guild"] = relationship(secondary=GuildRegion)

# class RegionalMessageBoard(Base):
#     __tablename__ = "rmb"

#     id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
#     author_id: Mapped[int] = mapped_column(ForeignKey("nations.id"))
#     region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
#     message: Mapped[str]
#     date: Mapped[int]

#     author: Mapped["Nation"] = relationship()
#     region: Mapped["Region"] = relationship()
