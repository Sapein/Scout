"""
This module contains all the stuff for NSVerify Functionality.
"""
import asyncio
import datetime
import logging
import json
from collections import OrderedDict
from typing import Any, Optional

import discord
import sqlalchemy.sql.functions
from discord.ext import commands, tasks
from discord.ext.commands import Context
from sqlalchemy import select, insert, update
from sqlalchemy.orm import Session

import Scout.nsapi.ns as ns
from Scout.core.nationstates import __VERSION__
from Scout.database.models import Region, Nation

utc = datetime.timezone.utc
time = datetime.time(hour=6, minute=00, tzinfo=utc)

logger = logging.getLogger("discord.cogs.core.nationstates")

class NationStates(commands.Cog):
    """A cog that provides various NationStates related functionality.

    Attributes:
        ns_client: The ns_client used for ns-api queries.
    """
    user_agent: Optional[str]
    ns_client: ns.NationStates_Client
    is_processing = False

    def __init__(self, bot, ns_client):
        """Initalizes the cog.

        Args:
            bot: The DiscordBot object.
        """
        self.scout = bot
        self.update_nations.start()
        self.update_nations_on_start.start()
        self.ns_client = ns_client

    @tasks.loop(count=1)
    async def update_nations_on_start(self):
        logger.info("Updating nations on start")
        await self.process_data_dump()
        logger.info("Updated nations")
        try:
            logger.info("Loading nsverify Cog")
            await self.scout.load_extension("Scout.core.nationstates.nsverify")
            logger.info("nsverify Cog loaded")
        except discord.ext.commands.ExtensionAlreadyLoaded:
            logger.warning("nsverify cog has already been loaded!")
        except (discord.ext.commands.ExtensionNotFound, discord.ext.commands.NoEntryPointError,
                discord.ext.commands.ExtensionFailed) as e:
            # Just take itself entirely down for now
            logger.error("Could not load nsverify cog! Error: %s", e)
            logger.info("NationStates Cog is being disabled.")
            logger.debug(e)
            logger.info("Disabling NationStates Cog...")
            self.scout.unload_extension("Scout.core.nationstates")
            logger.info("NationStates Cog Disabled.")

    @tasks.loop(time=time)
    async def update_nations(self):
        if not self.is_processing:
            logger.info("Running nightly update...")
            await self.process_data_dump()
            logger.info("Nightly update completed!")

    async def process_data_dump(self):
        """Handle the automatic update of nations.
        """
        self.is_processing = True
        logger.debug("Downloading Data Dumps")
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.ns_client.get_daily_dump("regions", user_agent=self.user_agent))
            tg.create_task(self.ns_client.get_daily_dump("nations", user_agent=self.user_agent))
        logger.debug("Data Dumps Downloaded!")

        dd = ns.NationStates_DataDump_Client()

        def add_regions(regions: OrderedDict[str, Any]):
            regions = regions["REGIONS"]["REGION"]
            with Session(self.scout.engine) as session:
                known_regions = {region.name: region.id for region in session.scalars(select(Region))}
                new_regions = ({'name': r["NAME"].casefold(), 'data': r} for r in regions if
                               r["NAME"].casefold() not in list(known_regions.keys()))
                old_regions = [{'id': known_regions[r["NAME"].casefold()], 'data': r,
                                'last_updated': datetime.datetime.now(datetime.UTC)}
                               for r in regions if r["NAME"].casefold() in list(known_regions.keys())]
                logger.debug("Adding regions")
                session.execute(insert(Region), new_regions)
                logger.debug("Updating regions")
                session.execute(update(Region), old_regions)
                session.commit()

        def add_nations(nations: OrderedDict[str, Any]):
            nations = nations["NATIONS"]["NATION"]
            with Session(self.scout.engine) as session:
                regions = {region.name: region.id for region in session.scalars(select(Region)).all()}
                known_nations = {nation.name: nation.id for nation in session.scalars(select(Nation)).all()}
                new_nations = ({'name': n["NAME"].casefold(), 'data': n,
                                'region_id': regions[n.data["REGION"].casefold()]}
                               for n in nations if n["NAME"].casefold() not in list(known_nations.keys()))
                old_nations = [{'id': known_nations[n["NAME"].casefold()], 'data': n,
                                'region_id': regions[n.data["REGION"].casefold()],
                                'last_updated': datetime.datetime.now(datetime.UTC)}
                               for n in nations if n["NAME"].casefold() in list(known_nations.keys())]
                logger.debug("Adding nations")
                session.execute(insert(Nation), new_nations)
                logger.debug("Updating nations")
                session.execute(update(Nation), old_nations)
                session.commit()

        logger.debug("Parsing Data Dumps...")
        async with asyncio.TaskGroup() as tg:
            regions = tg.create_task(dd.get_all_regions())
            nations = tg.create_task(dd.get_all_nations())
        logger.debug("Data Dumps Parsed...")
        regions = regions.result()
        nations = nations.result()

        logger.debug("Adding data to database")
        await asyncio.to_thread(add_regions,regions)
        await asyncio.to_thread(add_nations,nations)
        logger.debug("Data added to database")

        self.is_processing = False


    async def cog_load(self):
        """The function that the bot runs when the Cog is loaded.
        """
        user_agent = ns.create_user_agent(self.scout.config["CONTACT_INFO"],
                                          self.scout.config["NATION"],
                                          self.scout.config["REGION"])
        self.user_agent = "NationStates-Cog/{} {}".format(__VERSION__, user_agent)

    async def cog_unload(self) -> None:
        """Things to do when the cog is unloaded/at bot shutdown.
        """
        self.update_nations.stop()
        self.update_nations_on_start.stop()

    @commands.hybrid_command()  # type: ignore
    @commands.is_owner()
    async def dump(self, ctx: Context, nation_name: str):
        if self.is_processing:
            await ctx.send("Currently processing the data dumps...please wait")
            return
        with Session(self.scout.engine) as session:
            nation_data = session.scalar(select(Nation).where(Nation.name == nation_name.casefold()))
            await ctx.send("```json\n{}```".format(json.dumps(nation_data.data)))


async def setup(bot):
    """
    setup function to make this module into an extension.
    """
    logger.info("Adding the NationStates Cog.")
    await bot.add_cog(NationStates(bot, bot.ns_client))
    logger.info("NationStates Cod added.")
