import logging

import discord.ext.commands
import dice

logger = logging.getLogger("discord.cogs.plugins.dice")

@discord.ext.commands.hybrid_command(name="roll")  # type: ignore
async def roll(ctx: discord.ext.commands.Context, dice_notation: str):
    """Rolls a dice using dice notation
    """
    try:
        await ctx.send("Result: {}".format(dice.roll(dice_notation)))
    except (dice.exceptions.DiceException, dice.exceptions.DiceFatalException) as e:
        logger.error("Unable to roll dice...")
        logger.error(e)
        logger.debug(f"Exception: {e}")
        await ctx.send("Unable to roll dice. Reason: ```\n{}```".format(e.pretty_print()))


async def setup(bot: discord.ext.commands.Bot):
    """
    setup function to make this module into an extension.
    """
    bot.add_command(roll)
