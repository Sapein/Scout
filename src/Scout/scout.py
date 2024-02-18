"""
The main module for Scout.

This contains all the main 'logic' for the Discord Bot part of things.
"""

from typing import Optional, Any, Literal

import aiohttp
import discord
from discord.ext import commands
from discord.ext.commands import Context
from returns.result import Result, Success, Failure, safe
from sqlalchemy import Engine
from sqlalchemy.orm import Session

import Scout
from Scout import config
from Scout.database import db
from Scout.database.base import Base
from Scout.exceptions import *
from Scout.localization import ScoutTranslator
from Scout.nsapi import ns as ns

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
    ns_client: ns.NS_API_Client
    translator: ScoutTranslator

    async def on_ready(self):
        """Method to handle when the bot is ready.
        """
        self.reusable_session = aiohttp.ClientSession()
        self.engine = db.db_connect(dialect=self.config["DB_DIALECT"],
                                    driver=self.config.get("DB_DRIVER", None),
                                    table=self.config.get("DB_TABLE", None),
                                    login=self.config.get("DB_LOGIN", {'user': None, 'password': None}),
                                    connect=self.config.get("DB_CONN", {'host': None, 'port': None}))
        print("We are logged in as {}".format(self.user))
        Base.metadata.create_all(self.engine)
        self.translator = ScoutTranslator("scout")
        await self.tree.set_translator(self.translator)
        await self.load_extension("Scout.core.translations.translations")

        try:
            user_agent = ns.create_user_agent(self.config["CONTACT_INFO"],
                                              self.config["NATION"],
                                              self.config["REGION"])
            self.ns_client = ns.NationStates_Client(user_agent, self.reusable_session)
            # await self.load_extension("Scout.core.nationstates.nationstates")
            # await self.load_extension("Scout.core.nationstates.nsverify")
        except Exception as e:
            print(e)

        await self.load_extension("Scout.plugins.dice-rolls")
        await self.load_extension("Scout.plugins.simple-bump-leaderboard")
        await self.tree.sync()

    async def translate_response(self, ctx: commands.Context, response: str, **kwargs) -> str:
        """ A utility function for handling the translation and fallback for bot translations.

        Args:
            ctx: The message context
            response: The response to translate
            **kwargs: Things to add into the translated response.

        Returns:
            The translated string to send.

        Raises:
            TranslationError if an error occurs during translation.
        """
        is_interaction = ctx.interaction is not None
        is_in_server = ctx.guild is not None

        # Here be dragons!
        # This is a rather complex algorithm designed to determine what translation to use, if any.
        # Please note that this probably should be rewritten to be better, but until then here be dragons.
        # Abandon All Hope Yee Who Enter.
        if not is_in_server:
            with Session(self.engine) as session:
                user = db.get_user(ctx.author.id, session=session)
                if user is None or not user.locales and not is_interaction:
                    return await self.translator.translate_response(response, **kwargs)

                locales = [l.locale for l in sorted(list(user.locales), key=lambda x: x.priority)]

                if user.override_discord_locale and is_interaction:
                    locales.insert(0, ctx.interaction.locale)
                elif is_interaction:
                    locales.append(ctx.interaction.locale)

                for locale in locales:
                    if self.translator.check_supported(response, locale=locale, **kwargs):
                        return await self.translator.translate_response(response, locale=locale, **kwargs)
                return await self.translator.translate_response(response, **kwargs)

        elif is_in_server:
            with Session(self.engine) as session:
                guild_locale = ctx.guild.preferred_locale
                guild_db = db.get_guild(guild=ctx.guild.id, snowflake_only=True, session=session)

                if guild_db is None or not guild_db.locales:
                    prefer_user_locales = guild_db.override_user_locales if guild_db is not None else True

                    user = db.get_user(user=ctx.author.id, snowflake_only=True, session=session)
                    use_user_locales = user.use_locales_in_server if user is not None else False
                    prefer_user_locales = prefer_user_locales and use_user_locales

                    if prefer_user_locales:
                        user_locales = [l.locale for l in sorted(user.locales, key=lambda x: x.priority)]

                        if user.override_discord_locale and is_interaction:
                            user_locales.append(ctx.interaction.locale)
                        elif is_interaction:
                            user_locales.insert(0, ctx.interaction.locale)

                        locales = [*user_locales, guild_locale]
                        for locale in locales:
                            if self.translator.check_supported(response, locale=locale):
                                return await self.translator.translate_response(response, locale=locale, **kwargs)
                        return await self.translator.translate_response(response, **kwargs)
                    user_locales = [] if user is None else [l.locale
                                                            for l in sorted(user.locales, key=lambda x: x.priority)]

                    if user is not None and user.override_discord_locale and is_interaction:
                        user_locales.append(ctx.interaction.locale)
                    elif is_interaction:
                        user_locales.insert(0, ctx.interaction.locale)

                    locales = [guild_locale, *user_locales]
                    for locale in locales:
                        if await self.translator.check_supported(response, locale=locale):
                            return await self.translator.translate_response(response, locale=locale, **kwargs)
                    return await self.translator.translate_response(response, **kwargs)
                else:
                    user = db.get_user(user=ctx.author.id, snowflake_only=True, session=session)

                    use_user_locales = user.use_locales_in_server if user is not None else False
                    prefer_user_locales = guild_db.override_user_locales and use_user_locales

                    guild_locales = [l.locale for l in sorted(guild_db.locales, key=lambda x: x.priority)]
                    if prefer_user_locales:
                        user_locales = [] if user is None else [l.locale
                                                                for l in sorted(user.locales, key=lambda x: x.priority)]

                        if user is not None and user.override_discord_locale and is_interaction:
                            user_locales.append(ctx.interaction.locale)
                        elif is_interaction:
                            user_locales.insert(0, ctx.interaction.locale)

                        if guild_db.override_discord_locale:
                            guild_locales.append(guild_locale)
                        else:
                            guild_locales.insert(0, guild_locale)

                        locales = [*user_locales, *guild_locales]
                        for locale in locales:
                            if self.translator.check_supported(response, locale=locale):
                                return await self.translator.translate_response(response, locale=locale, **kwargs)
                        return await self.translator.translate_response(response, **kwargs)
                    user_locales = [] if user is None else [l.locale
                                                            for l in sorted(user.locales, key=lambda x: x.priority)]

                    if user is not None and user.override_discord_locale and is_interaction:
                        user_locales.append(ctx.interaction.locale)
                    elif is_interaction:
                        user_locales.insert(0, ctx.interaction.locale)

                    if guild_db.override_discord_locale:
                        guild_locales.append(guild_locale)
                    else:
                        guild_locales.insert(0, guild_locale)

                    locales = [*guild_locales, *user_locales]
                    for locale in locales:
                        if await self.translator.check_supported(response, locale=locale):
                            return await self.translator.translate_response(response, locale=locale, **kwargs)
                    return await self.translator.translate_response(response, **kwargs)

    @safe
    def register_association(self, association: str, *, session: Optional[Session] = None):
        """Register a role association with the bot.

        Parameters:
            association: The string representing what the role is being tied to.
            session: A DB session, if not provided the bot will create one.

        Returns:
            Result with either a Failure, or the association if successful.
        """
        if session is None:
            with Session(self.engine) as session:
                # noinspection PyArgumentList
                return self.register_association(association, session=session)

        if association in self.meanings:
            return Failure(AssociationRegistered(association))

        meaning_db = db.register_role_association(association, session=session)
        session.commit()
        self.meanings[association] = meaning_db.id
        return association

    @safe
    async def register_meaning_async(self, association: str, *, session: Optional[Session] = None):
        """An async wrapper around register_meaning.

        This is just a wrapper around the regular register_meaning function for the time being.

        Arguments:
            association: The 'role association' to register with the bot.
            session: The DB session to use to add the meaning to the database. If not provided, it will create one.

        Returns:
            Result: Success is The association registered, Failure if it failed to register the association.
        """
        # noinspection PyArgumentList
        return self.register_association(association, session=session)

    async def close(self, *args, **kwargs):
        """This is called when the bot is shutting down and closing connections.
        """
        await super().close(*args, **kwargs)
        await self.reusable_session.close()


_config = config.load_configuration()
scout = ScoutBot(command_prefix=_config["PREFIXES"], intents=intents)
scout.config = _config


@scout.listen('on_guild_role_update')
async def update_stored_roles(before: discord.Role, after: discord.Role):
    """Handles the updating of stored roles when they change.

    Parameters:
        before: The discord role before the update.
        after: The discord role after the update.
    """
    with Session(scout.engine) as session:
        role_db = db.get_role(before.id, snowflake_only=True, session=session)
        if before.id != after.id and role_db:
            role_db.snowflake = after.id
            session.commit()


@scout.listen('on_guild_role_delete')
async def remove_stored_roles(role: discord.Role):
    """Handles the removing of stored roles when they are deleted.

    Parameters:
        role: The role that has been removed.
    """
    with Session(scout.engine) as session:
        db.remove_role(role.id, snowflake_only=True, session=session)


@scout.listen('on_guild_remove')
async def remove_guild_info(guild: discord.Guild):
    """Handles the removing of guild information when the bot is kicked from a server.

    Parameters:
        guild: The guild the bot was kicked from.
    """
    with Session(scout.engine) as session:
        db.remove_guild(guild.id, snowflake_only=True, session=session)


@scout.hybrid_command()  # type: ignore
@commands.is_owner()
async def source(ctx):
    """The command to get a link to the bot's source code.

    Parameters:
        ctx: The command context.
    """
    await ctx.send(await scout.translate_response(ctx, "get-source", source=Scout.SOURCE))


@scout.hybrid_command()  # type: ignore
async def info(ctx):
    """The command to get the bot's information.

    Parameters:
        ctx: The command context.
    """
    await ctx.send(await scout.translate_response(ctx, "bot-info", version=Scout.__VERSION__, source=Scout.SOURCE))


@scout.hybrid_command()  # type: ignore
@commands.is_owner()
async def sync(ctx: Context,
               mode: Optional[Literal["guild", "global copy", "guild clear", "global"]]):
    """An owner-command to sync the bot's global command-tree to the command-tree of the guild.

    Parameters:
        ctx: The context of the command.
        mode: The mode of the sync. It can be a Literal of "guild", "global copy", "guild clear" and "global"
    """
    response = await ctx.send("Synchronizing...")
    match mode:
        case "guild":
            await ctx.bot.tree.sync(guild=ctx.guild)
        case "global copy":
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
        case "guild clear":
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
        case "global":
            await ctx.bot.tree.sync()
        case _:
            await ctx.bot.tree.sync(guild=ctx.guild)

    await response.edit(content=await scout.translate_response(ctx, "command-sync"))


@scout.hybrid_command()  # type: ignore
@commands.is_owner()
async def personality_set(ctx: Context, personality: str):
    """An owner command to set the bot's personality at run-time.

    Parameters:
        ctx: The context of the command.
        personality: The personality to use.
    """
    scout.translator.set_personality(personality)
    await ctx.send(await scout.translate_response(ctx, "personality-set"))


@scout.hybrid_group(name="ext", fallback="list")
@commands.is_owner()
async def list_ext(ctx: Context):
    """An owner-command to list bot extensions

    Parameters:
        ctx: The context of the command.
    """
    await ctx.send("\n".join(scout.extensions))


@list_ext.command(name="reload")
@commands.is_owner()
async def reload_ext(ctx: Context, extension: str):
    """An owner-command to reload bot extensions

    Parameters:
        ctx: The context of the command.
        extension: The extension to reload
    """
    loaded = []
    for ext in extension:
        await scout.reload_extension(ext)
        loaded.append(ext)
    await ctx.send("Reloaded Extensions:\n{}".format(extension))


@list_ext.command(name="load")
@commands.is_owner()
async def load_ext(ctx: Context, extension: str):
    """An owner-command to load bot extensions

    Parameters:
        ctx: The context of the command.
        extension: The extension to Load
    """
    await scout.load_extension(extension)
    await ctx.send("Loaded Extensions:\n{}".format(extension))


@list_ext.command(name="unload")
@commands.is_owner()
async def unload_ext(ctx: Context, extension: str):
    """An owner-command to load bot extensions

    Parameters:
        ctx: The context of the command.
        extension: The extension to Load
    """
    await scout.unload_extension(extension)
    await ctx.send("Unloaded Extensions:\n{}".format(extension))


@list_ext.command(name="reload-all")
@commands.is_owner()
async def reload_all_ext(ctx: Context):
    """An owner-command to reload bot extensions

    Parameters:
        ctx: The context of the command.
    """
    loaded = []
    for ext in [e for e in scout.extensions]:
        await scout.reload_extension(ext)
        loaded.append(ext)
    await ctx.send("Reloaded Extensions:\n{}".format("\n".join(loaded)))


@list_ext.command(name="unload-all")
@commands.is_owner()
async def unload_all_ext(ctx: Context):
    """An owner-command to reload bot extensions

    Parameters:
        ctx: The context of the command.
    """
    loaded = []
    for ext in [e for e in scout.extensions]:
        await scout.reload_extension(ext)
        loaded.append(ext)
    await ctx.send("Unloaded Extensions:\n{}".format("\n".join(loaded)))


scout.run(scout.config["DISCORD_API_KEY"])
