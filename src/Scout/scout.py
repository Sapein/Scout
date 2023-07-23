"""
The main module for Scout.

This contains all the main 'logic' for the Discord Bot part of things.
"""

from typing import Optional, Any

import aiohttp
import discord
from discord.ext import commands
from sqlalchemy import Engine
from sqlalchemy.orm import Session

import Scout
from Scout import config
from Scout.database import db, models
from Scout.database.base import Base
from Scout.exceptions import *
from Scout.localization import ScoutTranslator

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
    meanings: dict[str, int] = {}
    translator: ScoutTranslator

    async def on_ready(self):
        self.reusable_session = aiohttp.ClientSession()
        self.engine = db.db_connect(dialect=self.config["DB_DIALECT"],
                                    driver=self.config.get("DB_DRIVER", None),
                                    table=self.config.get("DB_TABLE", None),
                                    login=self.config.get("DB_LOGIN", {'user': None, 'password': None}),
                                    connect=self.config.get("DB_CONN", {'host': None, 'port': None}))
        print("We are logged in as {}".format(self.user))
        Base.metadata.create_all(self.engine)
        self.translator = ScoutTranslator("scout")
        await self.load_extension("Scout.core.nationstates.nsverify")
        await self.load_extension("Scout.core.translations.translations")
        await self.tree.set_translator(self.translator)
        await self.tree.sync()

    # async def translate_response(self, string: str, locale: Optional[Locale | str] = None, personality: Optional[str] = None,
    #                              **kwargs) -> Optional[str]:
    async def translate_response(self, ctx: commands.Context, response: str, **kwargs) -> str:
        async def handle_response(locale1: models.UserLocale, locale2: models.UserLocale) -> str:
            if locale1.priority > locale2.priority:
                _ = locale2
                locale2 = locale1
                locale1 = _

            if self.translator.check_supported(response, locale=locale1.locale):
                return await self.translator.translate_response(response, locale=locale1.locale, **kwargs)
            elif self.translator.check_supported(response, locale=locale2.locale):
                return await self.translator.translate_response(response, locale=locale2.locale, **kwargs)
            else:
                return await self.translator.translate_response(response, **kwargs)

        is_interaction = ctx.interaction is not None
        is_in_server = ctx.guild is not None

        # This is a non-interaction in a DM.
        if not is_interaction and not is_in_server:
            with Session(self.engine) as session:
                user = db.get_user(ctx.author.id, session=session)
                if user is None or not user.locales:
                    return await self.translator.translate_response(response, **kwargs)
                return await handle_response(user.locales.pop(), user.locales.pop())

        # This is an interaction in a DM.
        elif is_interaction and not is_in_server:
            with Session(self.engine) as session:
                user = db.get_user(ctx.author.id, session=session)
                discord_locale = ctx.interaction.locale
                if not user.override_discord_locale and self.translator.check_supported(response, locale=discord_locale):
                    return await self.translator.translate_response(response, locale=discord_locale, **kwargs)
                elif not user.override_discord_locale:
                    if user is None or not user.locales:
                        return await self.translator.translate_response(response, **kwargs)
                    return await handle_response(user.locales.pop(), user.locales.pop())

        # This is a non-interaction in a DM.
        elif not is_interaction and is_in_server:
            with Session(self.engine) as session:
                guild = db.get_guild(ctx.guild.id, session=session)
                preferred_locale = ctx.guild.preferred_locale
                if preferred_locale and guild is None:
                    if self.translator.check_supported(response, locale=preferred_locale):
                        return await self.translator.translate_response(response, locale=preferred_locale, **kwargs)

                    user = db.get_user(ctx.author.id, session=session)
                    if user is None or not user.locales:
                        return await self.translator.translate_response(response, **kwargs)
                    return await handle_response(user.locales.pop(), user.locales.pop())
                elif preferred_locale and guild is not None:
                    if guild.override_discord_locale:
                        pass

                elif not guild.override_discord_locale:
                    pass

        # This is an interaction in a DM.
        elif is_interaction and is_in_server:
            pass


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
    await ctx.send(
        await scout.translator.translate_response("bot-info", version=Scout.__VERSION__, source=Scout.SOURCE))


@scout.hybrid_command()  # type: ignore
@commands.is_owner()
async def sync(ctx):
    await scout.tree.sync(guild=ctx.guild)
    await ctx.send(await scout.translator.translate_response("command-sync"))


@scout.hybrid_command()  # type: ignore
@commands.is_owner()
async def personality_set(ctx, personality: str):
    scout.translator.set_personality(personality)
    await ctx.send(await scout.translator.translate_response("personality-set"))


scout.run(scout.config["DISCORD_API_KEY"])
