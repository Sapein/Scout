"""This is the database mappings for Scout to use."""
from typing import Optional, Any

import sqlalchemy.sql.functions
from datetime import datetime
from sqlalchemy import Table, Column, ForeignKey, Identity, Text
from sqlalchemy.orm import Mapped, relationship, mapped_column
#
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

role_associations = Table(
    "role_associations",
    Base.metadata,
    Column("association_id", ForeignKey("associations.id"), primary_key=True),
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


class Guild(Base):
    """ A mapping representing the Guild Database Table

    Attributes:
        id: The primary key and id of the Guild in the database.
        snowflake: The guild's discord snowflake
        override_discord_locale: If this is True then the bot will always prefer the guild's set locale.
        override_user_locales: If enabled on the guild, the bot will only respond in the guild's locales.

        regions: A set of all regions that are associated with the Guild.
        roles: A set of all roles that Scout uses/manages.
        locales: The server's Locales.
    """
    __tablename__ = "guilds"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    snowflake: Mapped[int] = mapped_column(unique=True, index=True)

    override_discord_locale: Mapped[bool] = mapped_column(default=False)
    override_user_locales: Mapped[bool] = mapped_column(default=False)

    regions: Mapped[set["Region"]] = relationship(secondary=guild_region, back_populates="guilds")
    roles: Mapped[set["Role"]] = relationship(back_populates="guild",
                                              cascade="save-update, merge, delete, delete-orphan")

    locales: Mapped[set["GuildLocale"]] = relationship(back_populates="guild", cascade="save-update, merge, delete")


class Role(Base):
    """Represents the role table in the database

    Attributes:
        id: The primary key and id of the role in the database.
        snowflake: The role's discord snowflake.
        guild_id: The guild the role is associated with.
        guild: The guild associated with the role.
        associations: The 'associations' for the role.
    """
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    snowflake: Mapped[int]

    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"))

    associations: Mapped[set["Association"]] = relationship(secondary=role_associations, back_populates="roles")
    guild: Mapped["Guild"] = relationship(back_populates="roles")


class Association(Base):
    """Represents the association table in the database.

    Associations are used to allow plugins to associate roles with internal information. These are handled by cogs/plugins/extensions.

    Attributes:
        id: The primary key and id of the role in the database.
        association: The association provided. This is just a string.
        roles: A set of roles associated with any given association.
    """
    __tablename__ = "associations"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    association: Mapped[str] = mapped_column(Text)

    roles: Mapped[set["Role"]] = relationship(secondary=role_associations, back_populates="associations",
                                              cascade="save-update, merge, delete")


class NationOwnershipInformation(Base):
    """Representation of nations on NationStates, and their data.

    Attributes:
        id: The primary key of the table.

        private: Whether the nation should automatically grant roles and whether it should be visible or not.
        added_on: When the nation was added to the database.
    """
    __tablename__ = "nation_ownership_information"
    id: Mapped[int] = mapped_column(ForeignKey("nations.id"), primary_key=True)
    private: Mapped[bool] = mapped_column(default=False)
    added_on: Mapped[datetime] = mapped_column(server_default=sqlalchemy.sql.functions.now())

    nation: Mapped["Nation"] = relationship(back_populates="verify_information")


class Nation(Base):
    """Representations of NationStates nations in the database.

    Attributes:
        id: The primary key and id of the Nation in our database.
        name: The name of the Nation in our database.
        last_updated: The timestamp of when the nation information was last updated.
        data: NationStates data in JSON form.
        region_id: The id of the Region in the database the nation is in.

        users: The users that have identified as this nation.
        region: The region that the nation is in.
        verify_information: Information based on NationStates Verify Options and Information.
    """
    __tablename__ = "nations"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    name: Mapped[str] = mapped_column(index=True, unique=True)
    last_updated: Mapped[datetime] = mapped_column(server_default=sqlalchemy.sql.functions.now())
    data: Mapped[dict[str, Any]]
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))

    users: Mapped[set["User"]] = relationship(secondary=user_nation, back_populates="nations")
    region: Mapped["Region"] = relationship(back_populates="nations")
    verify_information: Mapped["NationOwnershipInformation"] = relationship(back_populates="nation")


class Region(Base):
    """Representation of the NationStates region in the database.

    Attributes:
        id: The primary key and id of the region in our database.
        name: The name of the region in our database.
        last_updated: The timestamp of when the region information was last updated.
        data: The nationstates data of that region.
        nations: The set of nations that the bot knows about that are in the region.
        guilds: The set of guilds that a region is associated with.
    """
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Identity(increment=1), primary_key=True)
    name: Mapped[str] = mapped_column(index=True, unique=True)
    last_updated: Mapped[datetime] = mapped_column(server_default=sqlalchemy.sql.functions.now())
    data: Mapped[dict[str, Any]]

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

    first_seen: Mapped[datetime] = mapped_column(primary_key=True, server_default=sqlalchemy.sql.functions.now())
    last_seen: Mapped[Optional[datetime]] = mapped_column(default=None)

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
