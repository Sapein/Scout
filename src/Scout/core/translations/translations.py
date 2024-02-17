"""
This module contains all the stuff for localization/translations
"""
from typing import Optional

import discord.ext.commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm import Session

import Scout.exceptions
from Scout.database import db, models
from Scout.database.models import GuildLocale, UserLocale

PRIMARY = 1
SECONDARY = 2


class Translations(commands.Cog):
    """
    i18n/l10n commands Cog.
    """
    scout: Scout

    def __init__(self, bot):
        self.scout = bot

    async def cog_load(self):
        pass

    @staticmethod
    async def update_locale(obj: models.Guild | models.User, priority: int, language: str | None,
                            *, get_locale_priority, add_locale, get_locale_language, session: Session):
        """Provides a general interface for updating locale between servers and guilds.

        Arguments:
            obj: The database object to use that represents the guild/user.
            priority: the priority to put the locale/language at
            language: the locale/language to use.
            get_locale_priority: The function to use to get a locale for the obj at the specified priority.
            add_locale: The function to use to create the locale.
            get_locale_language: The function to use to get a UserLocale/GuildLocale for the specified language.
            session: DB Session.
        """
        lang = get_locale_priority(obj, priority, session=session)
        if language is None and lang is not None:
            session.delete(lang)
        elif language is not None and lang is None:
            locale = add_locale(obj, language, priority, session=session)
            session.add(locale)
        elif language is not None and lang is not None:
            if other := get_locale_language(obj, language, session=session):
                session.delete(lang)
                other.priority = priority
            else:
                lang.locale = language

    @commands.hybrid_command()  # type: ignore
    @commands.check_any(commands.has_guild_permissions(administrator=True), commands.is_owner())
    @commands.guild_only()
    async def set_server_language(self, ctx: discord.ext.commands.Context, language: Optional[str] = None,
                                  fallback_language: Optional[str] = None,
                                  override_locale: Optional[bool] = None, restrict_user_locales: Optional[bool] = None):
        """Set the language for the discord server (guild) in scout.

        Parameters:
            ctx: The message context
            language: The primary language to use.
            fallback_language: The fallback language to use.
            override_locale: Override the server's locale when possible.
            restrict_user_locales: If enabled, user locales will be restricted to language or fallback language.
        """
        if language is not None and language == fallback_language:
            await ctx.send("Can not set language and fallback language as the same!")
            return

        if not self.scout.translator.supports_locale(language):
            await ctx.send(f"Language {language} not supported!")
            return

        if fallback_language is not None and not self.scout.translator.supports_locale(fallback_language):
            await ctx.send(f"Language {language} not supported!")
            return

        with Session(self.scout.engine) as session:
            guild = db.get_guild(ctx.guild.id, snowflake_only=True, session=session)
            if guild is None:
                guild = db.register_guild(ctx.guild.id, session=session)
                session.add(guild)
                session.commit()

            original_discord = guild.override_discord_locale
            original_user = guild.override_user_locales
            guild.override_discord_locale = original_discord if override_locale is None else override_locale
            guild.override_user_locale = original_user if restrict_user_locales is None else restrict_user_locales
            # lang = get_locale_priority(obj, priority, session=session)
            # if language is None and lang is not None:
            #     session.delete(lang)
            # elif language is not None and lang is None:
            #     locale = add_locale(obj, language, priority, session=session)
            #     session.add(locale)
            # elif language is not None and lang is not None:
            #     if other := get_locale_language(obj, language, session=session):
            #         session.delete(lang)
            #         other.priority = priority
            #     else:
            #         lang.locale = language

            current_primary = session.scalar(select(GuildLocale)
                                             .where(GuildLocale.guild_id == guild.id)
                                             .where(GuildLocale.priority == PRIMARY))
            if language is None and current_primary is not None:
                session.delete(current_primary)
            elif language is not None and current_primary is None:
                new_locale = GuildLocale(guild_id=guild.id, priority=PRIMARY, locale=language)
                session.add(new_locale)
            elif language is not None and current_primary is not None:
                if other := session.scalar(select(GuildLocale).where(GuildLocale.guild_id == guild.id).where(GuildLocale.locale == language)):
                    session.delete(current_primary)
                    other.priority = PRIMARY
                else:
                    current_primary.locale = language

            current_fallback = session.scalar(select(GuildLocale)
                                             .where(GuildLocale.guild_id == guild.id)
                                             .where(GuildLocale.priority == SECONDARY))
            if language is None and current_fallback is not None:
                session.delete(current_fallback)
            elif language is not None and current_fallback is None:
                new_locale = GuildLocale(guild_id=guild.id, priority=SECONDARY, locale=language)
                session.add(new_locale)
            elif language is not None and current_fallback is not None:
                if other := session.scalar(select(GuildLocale).where(GuildLocale.guild_id == guild.id).where(GuildLocale.locale == language)):
                    session.delete(current_fallback)
                    other.priority = SECONDARY
                else:
                    current_fallback.locale = language
            session.commit()
            await ctx.send("Updated guild information!")

    @commands.hybrid_command()  # type: ignore
    async def set_language(self, ctx, language: str, fallback_language: Optional[str] = None,
                           override_locale: bool = False, use_in_servers: bool = False):
        """Set the language for the discord user with scout.

        Parameters:
            ctx: The message context
            language: The primary language to use.
            fallback_language: The fallback language to use.
            override_locale: Override the user's locale when possible.
            use_in_servers: If enabled, the user selected locales will be used in responses *IF* not disabled on the
                            server.
        """
        if language is not None and language == fallback_language:
            ctx.send("Can not set language and fallback language as the same!")
            return

        if not self.scout.translator.supports_locale(language):
            ctx.send(f"Language {language} not supported!")
            return

        if not self.scout.translator.supports_locale(fallback_language):
            ctx.send(f"Language {fallback_language} not supported!")
            return

        with Session(self.scout.engine) as session:
            user = db.get_user(ctx.user.id, session=session)
            if user is None:
                user = db.register_user(ctx.user.id, session=session)
                session.add(user)
                session.commit()

            original_discord = user.override_discord_locale
            original_server = user.use_locales_in_server
            user.override_discord_locale = original_discord if override_locale is None else override_locale
            user.restrict_server_locale = original_server if use_in_servers is None else use_in_servers

            current_primary = session.scalar(select(UserLocale)
                                             .where(UserLocale.user_id == user.id)
                                             .where(UserLocale.priority == PRIMARY))
            if language is None and current_primary is not None:
                session.delete(current_primary)
            elif language is not None and current_primary is None:
                new_locale = UserLocale(user_id=user.id, priority=PRIMARY, locale=language)
                session.add(new_locale)
            elif language is not None and current_primary is not None:
                if other := session.scalar(select(UserLocale).where(UserLocale.user_id == user.id).where(UserLocale.locale == language)):
                    session.delete(current_primary)
                    other.priority = PRIMARY
                else:
                    current_primary.locale = language

            current_fallback = session.scalar(select(UserLocale)
                                              .where(UserLocale.user_id == user.id)
                                              .where(UserLocale.priority == SECONDARY))
            if language is None and current_fallback is not None:
                session.delete(current_fallback)
            elif language is not None and current_fallback is None:
                new_locale = UserLocale(user_id=user.id, priority=SECONDARY, locale=language)
                session.add(new_locale)
            elif language is not None and current_fallback is not None:
                if other := session.scalar(select(UserLocale).where(UserLocale.user_id == user.id).where(UserLocale.locale == language)):
                    session.delete(current_fallback)
                    other.priority = SECONDARY
                else:
                    current_fallback.locale = language
            await ctx.send("Updated user information!")
            session.commit()


async def setup(bot):
    """
    setup function to make this module into an extension.
    """
    await bot.add_cog(Translations(bot))
