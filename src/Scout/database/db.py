"""
This is a more 'high level' of sorts DB interface.
"""
from functools import wraps
from typing import Optional, cast

from sqlalchemy import create_engine, select, or_, inspect
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

import Scout.database.exceptions
import Scout.database.models as models


def db_connect(dialect: str, driver: Optional[str], table: Optional[str], login: dict[str, Optional[str]],
               connect: dict[str, Optional[str | int]]):
    """
    Handles database connection stuff
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
    return create_engine(uri)


def readd(obj: object, session: Session) -> object:
    if inspect(obj).detached:
        session.add(session)
    return obj


def register_user(user_snowflake: int, *, session: Session) -> models.User:
    new_user = models.User(snowflake=user_snowflake)
    session.add(new_user)
    return new_user


def register_nation(nation: str, *, region_info: models.Region | int | str,
                    is_private: Optional[bool] = False, session: Session):
    if isinstance(region_info, str):
        output = session.scalar(select(models.Region.id).where(models.Region.name == region_info))
        if output is None:
            raise Scout.database.exceptions.RegionNameNotFound(
                "Region with name {} can not be found in db".format(region_info))
        region_info = output

    elif isinstance(region_info, int):
        if not session.scalar(select(models.Region.id).where(models.Region.id == region_info)):
            raise Scout.database.exceptions.RegionIdNotFound(
                "Region with ID {} not found in database".format(region_info))

    elif isinstance(region_info, models.Region):
        return models.Nation(name=nation, private=is_private, region=region_info, region_id=region_info.id)

    return models.Nation(name=nation, private=is_private, region_id=region_info)


def remove_nation(nation: int | models.Nation, *, session: Session):
    if isinstance(nation, int):
        nationdb = session.scalar(select(models.Nation).where(models.Nation.id == nation))
        if nationdb is None:
            raise Scout.database.exceptions.NationNotFound("Nation with ID {} not found".format(nation))
        nation = nationdb
    session.delete(nation)


def link_user_nation(user: models.User, nation: models.Nation, *, session) -> (models.User, models.Nation):
    readd(user, session)
    readd(nation, session)
    user.nations.add(nation)
    nation.users.add(user)
    return user, nation


def unlink_user_nation(user: models.User, nation: models.Nation, *, session: Session):
    readd(user, session)
    readd(nation, session)
    user.nations.remove(nation)


def register_guild(guild_snowflake: int, *, session: Session) -> models.Guild:
    new_guild = models.Guild(snowflake=guild_snowflake)
    session.add(new_guild)
    return new_guild


def remove_guild(guild: int | models.Guild, *, snowflake_only=False, session: Session):
    if isinstance(guild, int):
        guild_db = get_guild(guild, snowflake_only=snowflake_only, session=session)
        if guild_db is None:
            raise Scout.database.exceptions.GuildNotFound("Guild with id {} not found!".format(guild))
        guild = guild_db
    session.delete(guild)


def register_region(region_name: str, *, session: Session) -> models.Region:
    new_region = models.Region(name=region_name)
    session.add(new_region)
    return new_region


def remove_region(region: int | models.Guild, *, session: Session):
    if isinstance(region, int):
        region_db = get_region(region, session=session)
        if region_db is None:
            raise Scout.database.exceptions.RegionNotFound("Region with id {} not found!".format(region))
        region = region_db
    session.delete(region)


def link_guild_region(guild: models.Guild, region: models.Region, *, session: Session) -> (models.Guild, models.Region):
    readd(guild, session)
    readd(region, session)

    guild.regions.add(region)
    region.guilds.add(guild)

    return guild, region


def unlink_guild_region(guild: models.Guild, region: models.Region, *, session: Session):
    readd(guild, session)
    readd(region, session)

    guild.regions.remove(region)


def register_role(snowflake: str, *, guild: int | models.Guild, session: Session) -> models.Role:
    new_role: models.Role | None = None
    if isinstance(guild, int):
        new_role = models.Role(snowflake=snowflake, guild_id=guild)
    elif isinstance(guild, models.Guild):
        new_role = models.Role(snowflake=snowflake, guild=guild)

    session.add(new_role)
    return new_role


def remove_role(role: int | models.Role, *, snowflake_only=False, session: Session):
    if isinstance(role, int):
        role_db = get_role(role, snowflake_only=snowflake_only, session=session)
        if role_db is None:
            raise Scout.database.exceptions.RoleNotFound("Role with id: {} not found!".format(role))
        role = role_db
    session.delete(role)


def add_role_meaning(meaning: str, *, session: Session):
    new_meaning = models.Meaning(meaning=meaning.casefold())
    session.add(new_meaning)
    return new_meaning


def register_role_meaning(meaning: str, *, session: Session) -> models.Meaning:
    """
    Role Meanings
    """
    if (meaning_db := get_meaning(meaning, session=session)) is not None:
        return meaning_db
    return add_role_meaning(meaning, session=session)


def link_role_meaning(role: models.Role, meaning: models.Meaning, *, session: Session) -> (models.Role, models.Meaning):
    readd(meaning, session)
    readd(role, session)

    role.meanings.add(meaning)
    meaning.roles.add(role)

    return role, meaning


def get_user(user: int, *, snowflake_only=False, session: Session) -> models.User:
    if snowflake_only:
        return session.scalar(select(models.User).where(models.User.snowflake == user))
    return session.scalar(select(models.User).where(or_(models.User.id == user, models.User.snowflake == user)))


def get_guild(guild: int, *, snowflake_only=True, session: Session) -> models.Guild:
    if snowflake_only:
        return session.scalar(select(models.Guild).where(models.Guild.snowflake == guild))
    return session.scalar(
        select(models.Guild).where(or_(models.Guild.id == guild, models.Guild.snowflake == guild)))


def get_region(region: int | str, *, session: Session) -> models.Region:
    return session.scalar(select(models.Region).where(or_(models.Region.id == region, models.Region.name == region)))


def get_nation(nation: int | str, *, session: Session) -> models.Nation:
    return session.scalar(select(models.Nation).where(or_(models.Nation.id == nation, models.Nation.name == nation)))


def get_role(role: int, *, snowflake_only=False, session: Session) -> models.Role:
    if snowflake_only:
        return session.scalar(select(models.Role).where(models.Role.snowflake == role))
    return session.scalar(select(models.Role).where(or_(models.Role.id == role, models.Role.snowflake == role)))


def get_meaning(meaning: int | str, *, session: Session) -> models.Meaning:
    return session.scalar(
        select(models.Meaning).where(or_(models.Meaning.id == meaning, models.Meaning.meaning == meaning)))


def update_role(role: int | models.Role, new_snowflake: int, *, snowflake_only=False, session: Session) -> models.Role:
    if isinstance(role, int):
        role = get_role(role, snowflake_only=snowflake_only, session=session)
        if role is not None:
            raise Scout.database.exceptions.RoleNotFound("Role with ID or Snowflake {} not found!".format(role))

    role.snowflake = new_snowflake
    return role


def get_guildrole_with_meaning(guild: int | models.Guild, meaning: int | str | models.Meaning,
                               *, snowflake_only=True, session: Session) -> models.Role:
    if not isinstance(guild, models.Guild):
        guild = get_guild(guild, snowflake_only=snowflake_only, session=session)

    if not isinstance(meaning, models.Meaning):
        meaning = get_meaning(meaning, session=session)

    query = (select(models.Role)
             .where(models.Role.guild == guild)
             .join(models.role_meaning)
             .join(models.Meaning)
             .where(models.Meaning == cast(meaning, models.Meaning))
             .distinct())

    return session.scalar(query)


def add_user_locale(user: int | models.User, locale: str, priority: int,
                    *, snowflake_only=True, session: Session) -> models.UserLocale:
    if not isinstance(user, models.User):
        user = get_user(user, snowflake_only=snowflake_only, session=session)

    return models.UserLocale(user=user, locale=locale, priority=priority)


def get_user_locale_with_priority(user: int | models.User, priority: int,
                                  *, snowflake_only=True, session: Session) -> models.UserLocale:
    if not isinstance(user, models.User):
        user = get_user(user, snowflake_only=snowflake_only, session=session)

    return session.scalar(select(models.UserLocale)
                          .where(models.UserLocale.user_id == user.id)
                          .where(models.UserLocale.priority == priority)
                          .distinct()
                          .all())


def get_user_locale_with_language(user: int | models.User, locale: str,
                                  *, snowflake_only=True, session: Session) -> models.UserLocale:
    if not isinstance(user, models.User):
        user = get_user(user, snowflake_only=snowflake_only, session=session)

    return session.scalar(select(models.UserLocale)
                          .where(models.UserLocale.user_id == user.id)
                          .where(models.UserLocale.locale == locale)
                          .distinct()
                          .all())


def add_server_locale(user: int | models.Guild, locale: str, priority: int,
                      *, snowflake_only=True, session: Session) -> models.GuildLocale:
    if not isinstance(user, models.Guild):
        user = get_user(user, snowflake_only=snowflake_only, session=session)

    return models.GuildLocale(user=user, locale=locale, priority=priority)


def get_server_locale_with_priority(guild: int | models.Guild, priority: int,
                                    *, snowflake_only=True, session: Session) -> models.GuildLocale:
    if not isinstance(guild, models.Guild):
        guild = get_guild(guild, snowflake_only=snowflake_only, session=session)

    return session.scalar(select(models.GuildLocale)
                          .where(models.GuildLocale.guild_id == guild.id)
                          .where(models.GuildLocale.priority == priority)
                          .distinct()
                          .all())


def get_server_locale_with_language(guild: int | models.Guild, locale: str,
                                    *, snowflake_only=True, session: Session) -> models.GuildLocale:
    if not isinstance(guild, models.Guild):
        guild = get_guild(guild, snowflake_only=snowflake_only, session=session)

    return session.scalar(select(models.GuildLocale)
                          .where(models.GuildLocale.guild_id == guild.id)
                          .where(models.GuildLocale.locale == locale)
                          .distinct()
                          .all())
