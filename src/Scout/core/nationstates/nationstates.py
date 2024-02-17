"""
This module contains all the stuff for NSVerify Functionality.
"""
import asyncio
import datetime
import json
from collections import OrderedDict
from typing import Any, Optional

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
        await self.process_data_dump()

    @tasks.loop(time=time)
    async def update_nations(self):
        if not self.is_processing:
            await self.process_data_dump()

    async def process_data_dump(self):
        """Handle the automatic update of nations.
        """
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.ns_client.get_daily_dump("regions", user_agent=self.user_agent))
            tg.create_task(self.ns_client.get_daily_dump("nations", user_agent=self.user_agent))

        dd = ns.NationStates_DataDump_Client()

        def add_regions(regions: OrderedDict[str, Any]):
            regions = regions["REGIONS"]["REGION"]
            with Session(self.scout.engine) as session:
                known_regions = {region.name: region.id for region in session.scalars(select(Region)).all()}
                new_regions = ({'name': r["NAME"], 'data': r} for r in regions if
                               r["NAME"] not in list(known_regions.keys()))
                old_regions = [{'id': known_regions[r["NAME"]], 'name': r["NAME"], 'data': r, 'last_updated': sqlalchemy.sql.functions.now()} for r in regions if
                               r["NAME"] in list(known_regions.keys())]
                session.execute(insert(Region), new_regions)
                session.execute(update(Region), old_regions)
                session.commit()

        def add_nations(nations: OrderedDict[str, Any]):
            nations = nations["NATIONS"]["NATION"]
            with Session(self.scout.engine) as session:
                known_nations = {nation.name: nation.id for nation in session.scalars(select(Nation)).all()}
                new_nations = ({'name': n["NAME"], 'data': n, 'region_id': 0} for n in nations if
                               n["NAME"] not in list(known_nations.keys()))
                old_nations = [{'name': n["NAME"], 'data': n, 'region_id': 0, 'last_updated': sqlalchemy.sql.functions.now()} for n in nations if
                               n["NAME"] in list(known_nations.keys())]
                session.execute(insert(Nation), new_nations)
                session.execute(update(Nation), old_nations)
                session.commit()

        def associate():
            with Session(self.scout.engine) as session:
                regions = {region.name: region.id for region in session.scalars(select(Region)).all()}
                nations = [{'id': nation.id, 'name': nation.name, 'data': nation.data, 'region_id': regions[nation.data["REGION"]]} for nation in session.scalars(select(Nation)).all()]
                session.execute(update(Nation), nations)
                session.commit()

        async with asyncio.TaskGroup() as tg:
            regions = tg.create_task(dd.get_all_regions())
            nations = tg.create_task(dd.get_all_nations())
        regions = regions.result()
        nations = nations.result()

        self.is_processing = True
        async with asyncio.TaskGroup() as tg:
            tg.create_task(asyncio.to_thread(add_regions,regions))
            tg.create_task(asyncio.to_thread(add_nations,nations))

        await asyncio.to_thread(associate)
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

    @commands.hybrid_command()  # type: ignore
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
    await bot.add_cog(NationStates(bot, bot.ns_client))
