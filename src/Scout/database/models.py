"""
"""
import sqlalchemy.sql.functions
from sqlalchemy import Table, Column, ForeignKey, Identity, Text, DateTime
from sqlalchemy.orm import Mapped, relationship, mapped_column

from Scout.database.base import Base

user_nation = Table(
    "user_nations",
    Base.metadata,
    Column("nation_id", ForeignKey("nations.id"), primary_key=True),
    Column("user_id", ForeignKey("users.id"), primary_key=True)
)

guild_region = Table(
    "guild_regions",
    Base.metadata,
    Column("region_id", ForeignKey("regions.id"), primary_key=True),
    Column("guild_id", ForeignKey("guilds.id"), primary_key=True)
)

role_meaning = Table(
    "role_meanings",
    Base.metadata,
    Column("meaning_id", ForeignKey("meanings.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True)
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    snowflake: Mapped[int] = mapped_column(unique=True)

    nations: Mapped[set["Nation"]] = relationship(secondary=user_nation, back_populates="users",
                                                  cascade="save-update, merge, delete")


class Guild(Base):
    __tablename__ = "guilds"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    snowflake: Mapped[int] = mapped_column(unique=True, index=True)

    regions: Mapped[set["Region"]] = relationship(secondary=guild_region, back_populates="guilds")
    roles: Mapped[set["Role"]] = relationship(back_populates="guild",
                                              cascade="save-update, merge, delete, delete-orphan")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    snowflake: Mapped[int]

    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"))

    meanings: Mapped[set["Meaning"]] = relationship(secondary=role_meaning, back_populates="roles")
    guild: Mapped["Guild"] = relationship(back_populates="roles")


class Meaning(Base):
    __tablename__ = "meanings"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    meaning: Mapped[str] = mapped_column(Text)

    roles: Mapped[set["Role"]] = relationship(secondary=role_meaning, back_populates="meanings",
                                              cascade="save-update, merge, delete")


class Nation(Base):
    __tablename__ = "nations"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    name: Mapped[str] = mapped_column(index=True, unique=True)
    private: Mapped[bool] = mapped_column(default=False)
    added_on: Mapped[DateTime] = mapped_column(server_default=sqlalchemy.sql.functions.now())

    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))

    users: Mapped[set["User"]] = relationship(secondary=user_nation, back_populates="nations")
    region: Mapped["Region"] = relationship(back_populates="nations")


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    name: Mapped[str] = mapped_column(index=True, unique=True)

    nations: Mapped[set["Nation"]] = relationship(back_populates="region",
                                                  cascade="save-update, merge, delete, delete-orphan")
    guilds: Mapped[set["Guild"]] = relationship(secondary=guild_region, back_populates="regions")

# class RegionalMessageBoard(Base):
#     __tablename__ = "rmb"

#     id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
#     author_id: Mapped[int] = mapped_column(ForeignKey("nations.id"))
#     region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
#     message: Mapped[str]
#     date: Mapped[int]

#     author: Mapped["Nation"] = relationship()
#     region: Mapped["Region"] = relationship()
