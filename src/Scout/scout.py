"""
The main module for Scout.

This contains all the main 'logic' for the Discord Bot part of things.
"""

from typing import Optional, Any, cast

import aiohttp
import discord
from discord.app_commands import Translator
from discord.ext import commands
from sqlalchemy import Engine
from sqlalchemy.orm import Session

import Scout
from Scout import config
from Scout.database import db
from Scout.database.base import Base
from Scout.localization import ScoutTranslator
from Scout.exceptions import *

intents = discord.Intents.default()

intents.message_content = True
intents.members = True
intents.presences = True


class ScoutBot(commands.Bot):
    """
    The main Discord Bot Class
    """
    config: dict[str, Any]
    engine: Engine
    reusable_session: aiohttp.ClientSession
    meanings = {}
    translator: ScoutTranslator = ScoutTranslator()

    async def on_ready(self):
        self.reusable_session = aiohttp.ClientSession()
        self.engine = db.db_connect(dialect=self.config["DB_DIALECT"],
                                    driver=self.config.get("DB_DRIVER", None),
                                    table=self.config.get("DB_TABLE", None),
                                    login=self.config.get("DB_LOGIN", {'user': None, 'password': None}),
                                    connect=self.config.get("DB_CONN", {'host': None, 'port': None}))
        print("We are logged in as {}".format(self.user))
        Base.metadata.create_all(self.engine)
        await self.load_extension("Scout.core.nationstates.nsverify")
        await self.tree.set_translator(self.translator)
        await self.tree.sync()

    def register_meaning(self, meaning: str, *, suppress_error=False, session: Optional[Session] = None):
        if session is None:
            with Session(self.engine) as session:
                return self.register_meaning(meaning, suppress_error=suppress_error, session=session)

        if meaning in self.meanings and not suppress_error:
            raise MeaningRegistered(meaning)

        meaning_db = db.register_role_meaning(meaning, session=session)
        self.meanings[meaning] = meaning_db.id

    async def register_meaning_async(self, meaning: str, *, suppress_error=False, session: Optional[Session] = None):
        self.register_meaning(meaning, suppress_error=suppress_error, session=session)

    async def close(self, *args, **kwargs):
        await super().close(*args, **kwargs)
        await self.reusable_session.close()


_config = config.load_configuration()
scout = ScoutBot(command_prefix=_config["PREFIXES"], intents=intents)
scout.config = _config


@scout.listen('on_guild_role_update')
async def update_stored_roles(before: discord.Role, after: discord.Role):
    with Session(scout.engine) as session:
        role_db = db.get_role(before.id, snowflake_only=True, session=session)
        if before.id != after.id and role_db:
            role_db.snowflake = after.id
            session.commit()


@scout.listen('on_guild_role_delete')
async def remove_stored_roles(role: discord.Role):
    with Session(scout.engine) as session:
        db.remove_role(role.id, snowflake_only=True, session=session)


@scout.listen('on_guild_remove')
async def remove_guild_info(guild: discord.Guild):
    with Session(scout.engine) as session:
        db.remove_guild(guild.id, snowflake_only=True, session=session)


@scout.hybrid_command()  # type: ignore
@commands.is_owner()
async def source(ctx):
    await ctx.send(await scout.translator.translate_response("get-source", source=Scout.SOURCE))


@scout.hybrid_command()  # type: ignore
async def info(ctx):
    await ctx.send(await scout.translator.translate_response("bot-info", version=Scout.__VERSION__, source=Scout.SOURCE))


@scout.hybrid_command()  # type: ignore
@commands.is_owner()
async def sync(ctx):
    await scout.tree.sync(guild=ctx.guild)
    await ctx.send(await scout.translator.translate_response("command-sync"))


scout.run(scout.config["DISCORD_API_KEY"])
