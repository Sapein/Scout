"""This is the database mappings for Scout to use."""

import sqlalchemy.sql.functions
from datetime import datetime
from sqlalchemy import Table, Column, ForeignKey, Identity, Text
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
    """ A mapping representing the User Database Table

    Attributes:
        id: The primary key and id of the user in our database.
        snowflake: The user's discord snowflake
        override_discord_locale: If this is True then the bot will always prefer the user's set locale.
        use_locales_in_server: If enabled on the server, the bot will respond in the user's set/preferred locale.

        names: A set of all usernames in the UserNames table.
        nations: A set of all nations owned by the user.
        locales: The user's Locales.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    snowflake: Mapped[int] = mapped_column(unique=True)

    override_discord_locale: Mapped[bool] = mapped_column(default=False)
    use_locales_in_server: Mapped[bool] = mapped_column(default=False)

    names: Mapped[set["UserNames"]] = relationship(back_populates="user", cascade="save-update, merge, delete")
    nations: Mapped[set["Nation"]] = relationship(secondary=user_nation, back_populates="users",
                                                  cascade="save-update, merge, delete")

    locales: Mapped[set["UserLocale"]] = relationship(back_populates="user", cascade="save-update, merge, delete")


# class UserSettings(Base):
#     __tablename__ = "user_settings"
#     pass

class Guild(Base):
    """ A mapping representing the Guild Database Table

    Attributes:
        id: The primary key and id of the Guild in the database.
        snowflake: The guild's discord snowflake
        override_discord_locale: If this is True then the bot will always prefer the guild's set locale.
        restrict_user_locales: If enabled on the guild, the bot will only respond in the guild's locales.

        regions: A set of all regions that are associated with the Guild.
        roles: A set of all roles that Scout uses/manages.
        locales: The server's Locales.
    """
    __tablename__ = "guilds"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    snowflake: Mapped[int] = mapped_column(unique=True, index=True)

    override_discord_locale: Mapped[bool] = mapped_column(default=False)
    restrict_user_locales: Mapped[bool] = mapped_column(default=False)

    regions: Mapped[set["Region"]] = relationship(secondary=guild_region, back_populates="guilds")
    roles: Mapped[set["Role"]] = relationship(back_populates="guild",
                                              cascade="save-update, merge, delete, delete-orphan")

    locales: Mapped[set["GuildLocale"]] = relationship(back_populates="guild", cascade="save-update, merge, delete")


# class GuildSettings(Base):
#     __tablename__ = "guild_settings"
#     pass

class Role(Base):
    """Represents the role table in the database

    Attributes:
        id: The primary key and id of the role in the database.
        snowflake: The role's discord snowflake.
        guild_id: The guild the role is associated with.
        guild: The guild associated with the role.
        meanings: The 'meanings' associated with the role.
    """
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    snowflake: Mapped[int]

    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"))

    meanings: Mapped[set["Meaning"]] = relationship(secondary=role_meaning, back_populates="roles")
    guild: Mapped["Guild"] = relationship(back_populates="roles")


class Meaning(Base):
    """Represents the meanings table in the database.

    Meanings are basically just ways to tie why/what is being tracked with each role. These are handled by cogs/plugins.

    Attributes:
        id: The primary key and id of the role in the database.
        meaning: The meaning provided. This is just a string.
        roles: A set of roles associated with any given meaning.
    """
    __tablename__ = "meanings"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    meaning: Mapped[str] = mapped_column(Text)

    roles: Mapped[set["Role"]] = relationship(secondary=role_meaning, back_populates="meanings",
                                              cascade="save-update, merge, delete")


class Nation(Base):
    """Representations of the NationStates nation in the database.

    Attributes:
        id: The primary key and id of the Nation in our database.
        name: The name of the Nation in our database.
        private: Whether the nation should automatically grant roles and whether it should be visible or not.
        added_on: When the nation was added to the database.
        region_id: The id of the Region in the database the nation is in.

        users: The users that have identified as this nation.
        region: The region that the nation is in.
    """
    __tablename__ = "nations"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    name: Mapped[str] = mapped_column(index=True, unique=True)
    private: Mapped[bool] = mapped_column(default=False)
    added_on: Mapped[datetime] = mapped_column(server_default=sqlalchemy.sql.functions.now())

    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))

    users: Mapped[set["User"]] = relationship(secondary=user_nation, back_populates="nations")
    region: Mapped["Region"] = relationship(back_populates="nations")


class Region(Base):
    """Representation of the NationStates region in the database.

    Attributes:
        id: The primary key and id of the region in our database.
        name: The name of the region in our database.
        nations: The set of nations that the bot knows about that are in the region.
        guilds: The set of guilds that a region is associated with.
    """
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    name: Mapped[str] = mapped_column(index=True, unique=True)

    nations: Mapped[set["Nation"]] = relationship(back_populates="region",
                                                  cascade="save-update, merge, delete, delete-orphan")
    guilds: Mapped[set["Guild"]] = relationship(secondary=guild_region, back_populates="regions")


class UserNames(Base):
    """Representation of a log of every username that someone has gone by that the bot knows about.

    Attributes:
        user_id: The id of the user.
        name: The name recorded by the bot for the user.
        user: The user that is referred to by the user_id.
    """
    __tablename__ = "user_names"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    name: Mapped[str] = mapped_column(primary_key=True)

    user: Mapped["User"] = relationship(back_populates="names")


class UserLocale(Base):
    """Representation of the user set locales by the bot.

    Attributes:
        user_id: The id of the user this setting applies to.
        locale: The specific locale information.
        priority: The 'priority' to use, the lower the priority the better.
        user: The user the settings are for.
    """
    __tablename__ = "user_locales"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    locale: Mapped[str] = mapped_column(primary_key=True)
    priority: Mapped[int] = mapped_column(primary_key=True)

    user: Mapped["User"] = relationship(back_populates="locales")


# class GuildNames(Base):
#     __tablename__ = "guild_names"
#     pass

class GuildLocale(Base):
    """Representation of the guild set locales by the bot.

    Attributes:
        guild_id: The id of the guild this setting applies to.
        locale: The specific locale information.
        priority: The specific priority to use. The lower the priority the better.
        guild: The guild the settings are for.
    """
    __tablename__ = "guild_locale"

    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), primary_key=True)
    locale: Mapped[str] = mapped_column(primary_key=True)
    priority: Mapped[int] = mapped_column(primary_key=True)

    guild: Mapped["Guild"] = relationship(back_populates="locales")

# class RegionalMessageBoard(Base):
#     __tablename__ = "rmb"

#     id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
#     author_id: Mapped[int] = mapped_column(ForeignKey("nations.id"))
#     region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
#     message: Mapped[str]
#     date: Mapped[int]

#     author: Mapped["Nation"] = relationship()
#     region: Mapped["Region"] = relationship()
