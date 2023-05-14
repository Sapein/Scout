"""
The main module for Nerris.

This contains all the main 'logic' for the Discord Bot part of things.
"""

import asyncio

from typing import Self, Optional, Any, cast

import aiohttp
import discord
from discord.ext import commands

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy import select

import Nerris
import Nerris.database.exceptions as db_exception
from Nerris import config
from Nerris.database.base import Base
from Nerris.database import models as tbl
from Nerris.database import db
from Nerris.enums import RoleTypes
from Nerris.ns_api.nation import Nation
from Nerris.ns_api import ns
from Nerris.exceptions import *

intents = discord.Intents.default()

intents.message_content = True
intents.members = True
intents.presences = True


class NerrisBot(commands.Bot):
    """
    The main Discord Bot Class
    """
    config: dict[str, Any]
    database: db.Database
    reusable_session: aiohttp.ClientSession
    meanings = []
    meaning_ids = {RoleTypes.VERIFIED.value: None,
                   RoleTypes.RESIDENT.value: None}

    async def on_ready(self):
        self.reusable_session = aiohttp.ClientSession()
        self.database = db.Database(dialect=self.config["DB_DIALECT"],
                                    driver=self.config.get("DB_DRIVER", None),
                                    table=self.config.get("DB_TABLE", None),
                                    login=self.config.get("DB_LOGIN", {'user': None, 'password': None}),
                                    connect=self.config.get("DB_CONN", {'host': None, 'port': None}))
        print("We are logged in as {}".format(self.user))
        Base.metadata.create_all(self.database.engine)
        await self.load_extension("Nerris.core.nationstates.nsverify")
        await self.tree.sync()

    def register_meaning(self, meaning: str, *, suppress_error=False):
        if meaning in self.meanings and not suppress_error:
            raise MeaningRegistered(meaning)

        meaning_db = self.database.register_role_meaning(meaning)
        self.meanings.append(meaning)
        self.meaning_ids[meaning] = meaning_db.id

    async def register_meaning_async(self, meaning: str, *, suppress_error=False):
        if meaning in self.meanings and not suppress_error:
            raise MeaningRegistered(meaning)

        meaning_db = self.database.register_role_meaning(meaning)
        self.meanings.append(meaning)
        self.meaning_ids[meaning] = meaning_db.id

    def store_role(self, session: Session, role: discord.Role, guild: discord.Guild) -> Self:
        guild_db = self.database.get_guild(guild.id, snowflake_only=True, session=session)
        if guild_db is None:
            raise InvalidGuild(guild)

        self.database.register_role(role.id, guild_db, session=session)
        session.commit()
        return self

    def remove_role(self, role: discord.Role) -> Optional[discord.Role]:
        try:
            self.database.remove_role(role.id, snowflake_only=True)
            return role
        except db_exception.RoleNotFound:
            return None

    def add_role_meaning(self, session: Session, role: discord.Role, guild: discord.Guild, meaning: RoleTypes) -> Self:
        if meaning.value not in self.meaning_ids:
            raise InvalidMeaning(meaning)

        guild_db = self.database.get_guild(guild.id, snowflake_only=True, session=session)
        if not guild_db:
            raise InvalidGuild(guild)

        if role.id not in [r.snowflake for r in guild_db.roles]:
            raise InvalidRole(role)

        role_db = [r for r in guild_db.roles if r.snowflake == role.id][0]
        meaning_db = self.database.get_meaning(self.meaning_ids[meaning.value], session=session)
        if meaning_db is None:
            raise InvalidMeaning()
        role_db.meanings.add(meaning_db)
        session.commit()  # flush?
        return self

    async def verify_nation(self, nation_name: str, code: Optional[str]) -> tuple[str, Nation]:
        if code is None:
            raise NoCode_NSVerify()

        response, nation = await self.ns_client.verify(nation_name, code)
        if not response:
            raise InvalidCode_NSVerify(code)

        return "You're verified! Let me put this charactersheet in my campaign binder.", nation

    async def register_nation(self, nation: Nation, message: discord.Message) -> str:
        region = self.database.get_region(nation.region)
        if region is None:
            region = self.database.register_region(name=nation.region)

        user = self.database.register_user(snowflake=message.author.id)
        nation = self.database.register_nation(nation.name, region=region)
        self.database.link_user_nation(user, nation)
        return "There we go! I'll see if I can get you some roles..."

    async def give_verified_roles_one_guild(self, user: discord.User | discord.Member, guild: discord.Guild,
                                            noNationError=True):
        if isinstance(user, discord.User) or user.guild != guild:
            user = await guild.fetch_member(user.id)

        if not user:
            raise NotInGuild()

        guild_db = self.database.get_guild(guild.id, snowflake_only=True)
        if not guild_db:
            raise InvalidGuild()

        if not guild_db.roles:
            raise NoRoles()

        user_db = self.database.get_user(user.id, snowflake_only=True)
        if (user_db is None or not user_db.nations) and noNationError:
            raise NoNation()
        elif user_db is None:
            raise NoUser()

        if not guild_db.roles:
            raise NoRoles()

        shared_regions = guild_db.regions & {n.region for n in user_db.nations}

        resident_role = self.database.get_guildrole_with_meaning(guild_db, RoleTypes.RESIDENT.value.casefold())
        verified_role = self.database.get_guildrole_with_meaning(guild_db, RoleTypes.VERIFIED.value.casefold())

        if user_db.nations:
            if resident_role and verified_role:
                if user.get_role(resident_role.snowflake) and not shared_regions:
                    await user.remove_roles(discord.Object(resident_role.snowflake))
                    await user.add_roles(discord.Object(verified_role.snowflake))
                elif user.get_role(verified_role.snowflake) and shared_regions:
                    await user.remove_roles(discord.Object(verified_role.snowflake))
                    await user.add_roles(discord.Object(resident_role.snowflake))
                else:
                    await user.add_roles(discord.Object(verified_role.snowflake))
            elif resident_role:
                has_role = user.get_role(resident_role.snowflake)
                if not has_role and shared_regions:
                    await user.add_roles(discord.Object(resident_role.snowflake))
                elif has_role and not shared_regions:
                    await user.remove_roles(discord.Object(resident_role.snowflake))
            elif verified_role:
                if user.get_role(verified_role.snowflake):
                    await user.add_roles(discord.Object(verified_role.snowflake))
        else:
            if resident_role and verified_role:
                if user.get_role(resident_role.snowflake):
                    await user.remove_roles(discord.Object(resident_role.snowflake))
                if user.get_role(verified_role.snowflake):
                    await user.remove_roles(discord.Object(verified_role.snowflake))
            elif resident_role:
                has_role = user.get_role(resident_role.snowflake)
                if user.get_role(resident_role.snowflake):
                    await user.remove_roles(discord.Object(resident_role.snowflake))
            elif verified_role:
                if user.get_role(verified_role.snowflake):
                    await user.remove_roles(discord.Object(verified_role.snowflake))

    async def update_verified_roles(self, user: discord.User | discord.Member):
        with Session(self.database.engine) as session:
            if not session.scalars(select(tbl.Role)).all():
                raise NoRoles()

            mutual_guilds = {g.id: (g, m) for g in self.guilds if (m := await g.fetch_member(user.id))}

            active_guilds = session.scalars(
                select(tbl.Guild.snowflake).where(tbl.Guild.snowflake.in_(mutual_guilds.keys()))).all()
            if not active_guilds:
                raise NoGuilds()

            for guild_snowflake in active_guilds:
                try:
                    await self.give_verified_roles_one_guild(mutual_guilds[guild_snowflake][1],
                                                             mutual_guilds[guild_snowflake][0], noNationError=False)
                except NotInGuild:
                    pass

    async def give_verified_roles(self, user: discord.User | discord.Member):
        with Session(self.database.engine) as session:
            if not session.scalars(select(tbl.Role)).all():
                raise NoRoles()

            mutual_guilds = {g.id: (g, m) for g in self.guilds if (m := await g.fetch_member(user.id))}

            active_guilds = session.scalars(
                select(tbl.Guild.snowflake).where(tbl.Guild.snowflake.in_(mutual_guilds.keys()))).all()
            if not active_guilds:
                raise NoGuilds()

            for guild_snowflake in active_guilds:
                try:
                    await self.give_verified_roles_one_guild(mutual_guilds[guild_snowflake][1],
                                                             mutual_guilds[guild_snowflake][0])
                except NotInGuild:
                    pass

    def add_role(self, role: discord.Role, guild: discord.Guild, meaning: str | RoleTypes, *, override: Optional[bool] = False):
        guild_db = self.database.get_guild(guild.id, snowflake_only=True)
        if not guild_db:
            raise InvalidGuild()

        if (role_db := self.database.get_guildrole_with_meaning(guild_db, cast(str, meaning))) is not None:
            if not override:
                raise RoleOverwrite(role)
            return self.database.update_role(role_db, role.id)

        role = nerris.database.register_role(role.id, guild_db)
        meaning = nerris.database.get_meaning(meaning)

        if meaning is None:
            raise InvalidMeaning(meaning)

        nerris.database.link_role_meaning(role, meaning)

    async def close(self, *args, **kwargs):
        await super().close(*args, **kwargs)
        await self.reusable_session.close()


_config = config.load_configuration()
nerris = NerrisBot(command_prefix=_config["PREFIXES"], intents=intents)
nerris.config = _config


@nerris.hybrid_command()  # type: ignore
async def verified_nations(ctx, private_response: Optional[bool] = True):
    """
    Displays Verified Nations of a given user.
    """
    user = nerris.database.get_user(ctx.message.author.id, snowflake_only=True)
    if user is not None and user.nations:
        await ctx.send('\n'.join([n.name for n in user.nations]), ephemeral=private_response)
    await ctx.send("I don't have any nations for you!")


@nerris.listen('on_member_join')
async def verify_on_join(member: discord.Member):
    with Session(nerris.database.engine) as session:
        await nerris.give_verified_roles_one_guild(member, member.guild)


@nerris.listen('on_guild_role_update')
async def update_stored_roles(before: discord.Role, after: discord.Role):
    with Session(nerris.database.engine) as session:
        role_db = nerris.database.get_role(before.id, snowflake_only=True, session=session)
        if before.id != after.id and role_db:
            role_db.snowflake = after.id
            session.commit()


@nerris.listen('on_guild_role_delete')
async def remove_stored_roles(role: discord.Role):
    nerris.database.remove_role(role.id, snowflake_only=True)


@nerris.listen('on_guild_remove')
async def remove_guild_info(guild: discord.Guild):
    nerris.database.remove_guild(guild.id, snowflake_only=True)


@nerris.hybrid_command()  # type: ignore
@commands.is_owner()
async def source(ctx):
    await ctx.send("You can find my source code here! {}".format(Nerris.SOURCE))


@nerris.hybrid_command()  # type: ignore
async def info(ctx):
    info_string = (
        "I'm Nerris Version {}!\n"
        "I am a bot created for The Campfire discord server and the associated NS region Sun's Reach!\n"
        "I mostly just help manage nation verification at this time.\n"
        "Now where did my D20 go..."
    ).format(Nerris.__VERSION__)
    await ctx.send(info_string)


@nerris.hybrid_command()  # type: ignore
@commands.is_owner()
async def sync(ctx):
    await nerris.tree.sync(guild=ctx.guild)
    await ctx.send("Synced Slash Commands to Server!")


nerris.run(nerris.config["DISCORD_API_KEY"])
