"""
This is a more 'high level' of sorts DB interface.
"""
from functools import wraps
from typing import Optional, cast

from sqlalchemy import create_engine, Engine, select, or_, inspect
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

import Nerris.database.models as models

import Nerris.database.exceptions


class Database:
    engine: Engine

    def __init__(self, dialect: str, driver: Optional[str], table: Optional[str], login: dict[str, Optional[str]],
                 connect: dict[str, Optional[str | int]]):
        """
        Handles database conenction stuff
        """
        driver_name = dialect
        if driver:
            driver_name = "{}+{}".format(driver_name, driver)

        uri = URL.create(driver_name,
                         username=login.get('user', None),
                         password=login.get('password', None),
                         host=cast(Optional[str], connect.get('host', None)),
                         port=cast(Optional[int], connect.get('port', None)),
                         database=table)
        self.engine = create_engine(uri)

    def readd(self, obj, session: Session) -> obj:
        if inspect(obj).detached:
            session.add(session)
        return obj

    def _check(self, _func, *, add_commit=True, no_add=False):
        def wrapper(func):
            @wraps(func)
            def perform_check(*args, **kwargs):
                def session_add(val):
                    if val is None or no_add: return
                    try:
                        kwargs['session'].add_all([*val])
                    except TypeError:
                        kwargs['session'].add(val)

                if self.engine is None:
                    raise ValueError("You must initialize the object!")

                if 'session' not in kwargs or kwargs['session'] is None:
                    with Session(self.engine) as session:
                        kwargs['session'] = session
                        result = func(*args, **kwargs)
                        if not add_commit: return result
                        session_add(result)
                        session.commit()
                        return result
                result = func(*args, **kwargs)
                if not add_commit: return result
                session_add(result)
                return result

            return perform_check

        if _func is None:
            return wrapper
        else:
            return wrapper(_func)

    @_check
    def register_user(self, user_snowflake: int, *, session: Optional[Session] = None) -> models.User:
        return models.User(snowflake=user_snowflake)

    @_check(no_add=True)
    def remove_user(self, user: int | models.User, *, session: Optional[Session] = None):
        match user:
            case int():
                userdb = session.scalar(select(models.User).where(models.User.id == user))
                if userdb is None:
                    raise Nerris.database.exceptions.UserNotFound("User with user ID {} not found!".format(user))
                user = userdb
            case models.User():
                pass
        session.delete(user)

    @_check
    def register_nation(self, nation: str, *, region_info: models.Region | int | str,
                        is_private: Optional[bool] = False, session: Optional[Session]):
        match region_info:
            case str():
                output = session.scalar(select(models.Region.id).where(models.Region.name == region_info))
                if output is None:
                    raise Nerris.database.exceptions.RegionNameNotFound(
                        "Region with name {} can not be found in db".format(region_info))
                region_info = output

            case int():
                if not session.scalar(select(models.Region.id).where(models.Region.id == region_info)):
                    raise Nerris.database.exceptions.RegionIdNotFound(
                        "Region with ID {} not found in database".format(region_info))

            case models.Region():
                return models.Nation(name=nation, private=is_private, region=region_info, region_id=region_info.id)

        return models.Nation(name=nation, private=is_private, region_id=region_info)

    @_check(no_add=True)
    def remove_nation(self, nation: int | models.Nation, session: Optional[Session] = None):
        match nation:
            case int():
                nationdb = session.scalar(select(models.Nation).where(models.Nation.id == nation))
                if nationdb is None:
                    raise Nerris.database.exceptions.NationNotFound("Nation with ID {} not found".format(nation))
                nation = nationdb
            case models.Nation():
                pass
        session.delete(nation)

    @_check
    def link_user_nation(self, user: models.User, nation: models.Nation, *, session=None) -> (
            models.User, models.Nation):
        self.readd(user, session)
        self.readd(nation, session)
        user.nations.add(nation)
        nation.users.add(user)
        return user, nation

    @_check(no_add=True)
    def unlink_user_nation(self, user: models.User, nation: models.Nation, *, session: Optional[Session] = None):
        self.readd(user, session)
        self.readd(nation, session)
        user.nations.remove(nation)

    @_check
    def register_guild(self, guild_snowflake: int, *, session: Optional[Session] = None) -> models.Guild:
        return models.Guild(snowflake=guild_snowflake)

    @_check(no_add=True)
    def remove_guild(self, guild: int | models.Guild, *, snowflake_only=False, session: Optional[Session] = None):
        match guild:
            case int():
                guild_db = self.get_guild(guild, snowflake_only=snowflake_only, session=session)
                if guild_db is None:
                    raise Nerris.database.exceptions.GuildNotFound("Guild with id {} not found!".format(guild))
                guild = guild_db
            case models.Guild():
                pass
        session.delete(guild)

    @_check
    def register_region(self, region_name: str) -> models.Region:
        return models.Region(name=region_name)

    @_check(no_add=True)
    def remove_region(self, region: int | models.Guild, *, snowflake_only=False, session: Optional[Session] = None):
        match region:
            case int():
                region_db = self.get_region(region, snowflake_only=snowflake_only, session=session)
                if region_db is None:
                    raise Nerris.database.exceptions.RegionNotFound("Region with id {} not found!".format(region))
                region = region_db
            case models.Region():
                pass
        session.delete(region)

    @_check
    def link_guild_region(self, guild: models.Guild, region: models.Region, *, session=None) -> (
            models.Guild, models.Region):
        self.readd(guild, session)
        self.readd(region, session)

        guild.regions.add(region)
        region.guilds.add(guild)
        return guild, region

    @_check(no_add=True)
    def unlink_guild_region(self, guild: models.Guild, region: models.Region, *, session: Optional[Session] = None):
        self.readd(guild, session)
        self.readd(region, session)
        guild.regions.remove(region)

    @_check
    def register_role(self, snowflake: str, *, guild: int | models.Guild,
                      session: Optional[Session] = None) -> models.Role:
        match guild:
            case int():
                return models.Role(snowflake=snowflake, guild_id=guild)
            case models.Guild():
                return models.Role(snowflake=snowflake, guild=guild)

    @_check(no_add=True)
    def remove_role(self, role: int | models.Role, *, snowflake_only=False, session: Optional[Session] = None):
        match role:
            case int():
                role_db = self.get_role(role, snowflake_only=snowflake_only, session=session)
                if role_db is None:
                    raise Nerris.database.exceptions.RoleNotFound("Role with id: {} not found!".format(role))
                role = role_db
            case models.Role():
                pass
        session.delete(role)

    @_check
    def add_role_meaning(self, meaning: str, *, session: Optional[Session] = None):
        return models.Meaning(meaning=meaning.casefold())

    @_check(add_commit=False)
    def register_role_meaning(self, meaning: str, *, session: Optional[Session] = None) -> models.Meaning:
        """
        Role Meanings
        """
        if (meaning_db := self.get_meaning(meaning, session=session)) is not None:
            return meaning_db
        return self.add_role_meaning(meaning, session=session)

    @_check
    def link_role_meaning(self, role: models.Role, meaning: models.Meaning) -> (models.Role, models.Meaning):
        role.meanings.add(meaning)
        meaning.roles.add(role)
        return role, meaning

    @_check(add_commit=False)
    def get_user(self, user: int, *, snowflake_only=False, session: Optional[Session] = None) -> models.User:
        if snowflake_only:
            return session.scalar(select(models.User).where(models.User.snowflake == user))
        return session.scalar(select(models.User).where(or_(models.User.id == user, models.User.snowflake == user)))

    @_check(add_commit=False)
    def get_guild(self, guild: int, *, snowflake_only=True, session: Optional[Session] = None) -> models.Guild:
        if snowflake_only:
            return session.scalar(select(models.Guild).where(models.Guild.snowflake == guild))
        return session.scalar(
            select(models.Guild).where(or_(models.Guild.id == guild, models.Guild.snowflake == guild)))

    @_check(add_commit=False)
    def get_region(self, region: int | str, *, session: Optional[Session] = None) -> models.Region:
        return session.scalar(
            select(models.Region).where(or_(models.Region.id == region, models.Region.name == region)))

    @_check(add_commit=False)
    def get_nation(self, nation: int | str, *, session: Optional[Session] = None) -> models.Nation:
        return session.scalar(
            select(models.Nation).where(or_(models.Nation.id == nation, models.Nation.name == nation)))

    @_check(add_commit=False)
    def get_role(self, role: int, *, snowflake_only=False, session: Optional[Session] = None) -> models.Role:
        if snowflake_only:
            return session.scalar(select(models.Role).where(models.Role.snowflake == role))
        return session.scalar(select(models.Role).where(or_(models.Role.id == role, models.Role.snowflake == role)))

    @_check(add_commit=False)
    def get_meaning(self, meaning: int | str, *, session: Optional[Session] = None) -> models.Meaning:
        return session.scalar(
            select(models.Meaning).where(or_(models.Meaning.id == meaning, models.Meaning.meaning == meaning)))

    @_check(no_add=True)
    def update_role(self, role: int | models.Role, new_snowflake: int, *, snowflake_only=False,
                    session: Optional[Session] = None) -> models.Role:
        if isinstance(role, int):
            role = self.get_role(role, snowflake_only=snowflake_only, session=session)
            if role is not None:
                raise Nerris.database.exceptions.RoleNotFound("Role with ID or Snowflake {} not found!".format(role))

        role.snowflake = new_snowflake
        return role

    @_check(add_commit=False)
    def get_guildrole_with_meaning(self, guild: int | models.Guild, meaning: int | str | models.Meaning,
                                   *, snowflake_only=True, session: Optional[Session] = None) -> models.Role:
        if not isinstance(guild, models.Guild):
            guild = self.get_guild(guild, snowflake_only=snowflake_only)

        if not isinstance(meaning, models.Meaning):
            meaning = self.get_meaning(meaning)

            query = (select(models.Role)
                     .where(models.Role.guild == guild)
                     .join(models.role_meaning)
                     .join(models.Meaning)
                     .where(models.Meaning == meaning)
                     .distinct())

            return session.scalar(query)
