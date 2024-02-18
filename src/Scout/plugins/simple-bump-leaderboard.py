import logging
from typing import Optional

import discord
from discord import InteractionType, Embed
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm import Session

from Scout.database.base import Base
from Scout.plugins.simple_bump_leaderboard_models import BumpLeaderBoard, BumpLog

logger = logging.getLogger("discord.cogs.plugins.simple_bump_leaderboard")

class SimpleBumpLeaderboard(commands.Cog):
    def __init__(self, bot):
        self.scout = bot
        Base.metadata.create_all(self.scout.engine)

    @commands.Cog.listener('on_message')
    async def on_message(self, message: discord.Message):
        cant_run = message.interaction is None
        cant_run = cant_run or message.interaction.type != InteractionType.application_command
        cant_run = cant_run or message.interaction.name != "bump"
        cant_run = cant_run or "disboard".casefold() not in message.author.name.casefold() or cant_run
        if cant_run:
            return

        with Session(self.scout.engine) as session:
            author_id = message.interaction.user.id
            guild_id = message.guild.id
            entry = session.scalar(select(BumpLeaderBoard).where(BumpLeaderBoard.user_snowflake == author_id).where(
                BumpLeaderBoard.guild_snowflake == guild_id))
            if entry is None:
                entry = BumpLeaderBoard(guild_snowflake=guild_id, user_snowflake=author_id)
                session.add(entry)
                session.commit()

            entry.bump_count += 1
            session.add(BumpLog(guild_snowflake=guild_id, user_snowflake=author_id))
            session.commit()

    @commands.hybrid_command()  # type: ignore
    async def show_leaderboard(self, ctx, limit: Optional[int] = 10):
        if limit == 0:
            await ctx.send("Limit can not be 0", ephemeral=True)
            return

        with Session(self.scout.engine) as session:
            top_bumpers = session.scalars(select(BumpLeaderBoard).order_by(BumpLeaderBoard.bump_count.desc()
                                                                           ).limit(limit)).all()
            if top_bumpers is None or len(top_bumpers) == 0:
                bumper_embed = Embed(title="Top Server Bumpers!", description="No one is on the leaderboard yet!")
                await ctx.send(embed=bumper_embed)
                return

            _top_bumpers = top_bumpers
            top_bumpers = [f"{i + 1}. <@{t.user_snowflake}> - {t.bump_count}" for (i, t) in enumerate(top_bumpers)]
            top_bumpers[0] = top_bumpers[0].replace("1.", ":crown:")
            try:
                top_bumpers[1] = top_bumpers[1].replace("2.", ":second_place:")
            except IndexError:
                pass

            try:
                top_bumpers[2] = top_bumpers[2].replace("3.", ":third_place:")
            except IndexError:
                pass
            # top_bumpers = [t.replace("{} ", "") for t in top_bumpers]
            top_bumper_embed = Embed(title="Top Server Bumpers!", description="\n".join(top_bumpers))
            await ctx.send(embed=top_bumper_embed, allowed_mentions=discord.AllowedMentions.none())


async def setup(bot: discord.ext.commands.Bot):
    """
    setup function to make this module into an extension.
    """
    await bot.add_cog(SimpleBumpLeaderboard(bot))
