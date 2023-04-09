"""
"""

import discord
import os

import aiohttp
import asyncio

from sqlalchemy.orm import Session
from sqlalchemy import select
from Nerris.database.base import Base

import Nerris
import Nerris.database.tables as tbl
import Nerris.database.db as db

from typing import Optional

from discord.ext import commands
from Nerris.enums import RoleTypes
import Nerris.nationstates.ns as ns

from result import Err, Ok, Result

from Nerris.exceptions import *

intents = discord.Intents.default()
intents.message_content = True

class NerrisBot(commands.Bot):
    db_engine = db.connect(in_memory=True)
    users_verifying = {}

    async def on_ready(self, *args, **kwargs):
        self.aiohttp_session = aiohttp.ClientSession()
        self.ns_client = await ns.NationStatesClient(self.aiohttp_session).build()
        print("We are logged in as {}".format(self.user))
        Base.metadata.create_all(self.db_engine)
        await self.tree.sync()


    def register_meanings(self):
        with Session(self.db_engine) as session:
            verified_role = tbls.Meaning(meaning=RoleTypes.VERIFIED.casefold())
            resident_role = tbls.Meaning(meaning=RoleTypes.RESIDENT.casefold())

    def store_role(self, session: Session, role: discord.Role, guild: discord.Guild):
        guild_id = session.scalar(select(tbl.Guild).where(tbl.Guild.snowflake == guild.id))
        if not guild_id:
            raise NoGuild(guild)
        new_role = tbl.Role(snowflake = role.id, guild_id=guild_id)
        session.add(new_role)
        session.commit()

    def add_role_meaning(self, session: Session, role: discord.Role, guild: discord.Guild, meaning: RoleTypes):
        meaning = session.scalar(select(tbl.Meaning).where(tbl.Meaning.meaning == meaning.casefold()))
        if not meaning:
            raise NoMeaning(meaning)

        guild = session.scalar(select(tbl.Guild).where(tbl.Guild.snowflake == guild.id))
        if not guild:
            raise NoGuild(guild)

        role = session.scalar(select(tbl.Role).where(tbl.Role.snowflake == role.id and tbl.Row.guild_id == guild.id))
        if not role:
            raise NoRole(role)

        role_meaning = tbl.RoleMeaning(meaning_id = meaning.id, role_id = role.id)
        session.add(role)
        session.commit()


    def verify_nation(self, ctx):
        pass

    def _link_roles(self, verified_role: Optional[discord.Role], resident_role: Optional[discord.Role], message: discord.Message) -> str:
        with Session(nerris.db_engine) as session:
            if verified_role is None and resident_role is None:
                raise NoRoles()

            if verified_role is not None:
                nerris.store_role(session, verified_role, message.guild)
                nerris.add_role_meaning(session, verified_role, message.guild, RoleType.VERIFIED)

            if resident_role is not None:
                nerris.store_role(session, resident_role, message.guild)
                nerris.add_role_meaning(session, verified_role, message.guild, RoleType.RESIDENT)

            if verified_role is not None and resident_role is not None:
                return ("A Natural 20, a critical success! I've obtained the mythical +1 roles of {} and {}!"
                       ).format(verified_role.name, resident_role.name)
            if verified_role is not None:
                return("Looks like I found the mythical role of {}...now to find the other piece."
                      ).format(verified_role)
            return ("Looks like I found the mythical role of {}...now to find the other piece."
                   ).format(resident_role)

    async def close(self, *args, **kwargs):
        await super().close(*args, **kwargs)
        await self.aiohttp_session.close()

nerris = NerrisBot(command_prefix = ".", intents=intents)

@nerris.hybrid_command()
async def verified_nations(ctx):
    """
    Displays Verified Nations of a given user.
    """
    await ctx.send(nation)

@nerris.hybrid_command()
@commands.guild_only()
async def verify_nation(ctx, nation: str):
    """
    Verifies a nation and assigns it to a user.
    """
    with Session(nerris.db_engine) as session:
        if session.scalars(select(tbl.Nation).where(tbl.Nation.name == nation.replace(" ", "_"))).all():
            await ctx.send("This nation has already been registered silly!", ephemeral=True)
            return
    nerris.users_verifying[ctx.message.author] = nation
    await ctx.send("Alrighty! Please check your DMs", ephemeral=True)
    await ctx.message.author.send(("Hi please log into your {} now. After doing so go to this link: {}\n"
                                   "Copy the code from that page and paste it here.\n"
                                   "**__This code does not give anyone access to your nation or any control over it. It only allows me to verify identity__**\n"
                                   "Pretty cool, huh?").format(nation, nerris.ns_client.get_verify_url()))

    await asyncio.sleep(60)
    if ctx.message.author in nerris.users_verifying:
        await ctx.message.author.send(("Oh, you didn't want to verify? That's fine. If you change your mind just `/verify_nation` again!"))
        del nerris.users_verifying[message.author]

@nerris.listen('on_message')
async def verify_nation(message):
    if message.guild is None and message.author in nerris.users_verifying:
        nation = nerris.users_verifying[message.author]
        if code := message.content:
            response, nation = await nerris.ns_client.verify(nation, code)
            if response:
                await message.author.send("Now you're verified! I'll make you a charactersheet!")

                with Session(nerris.db_engine) as session:
                    region_id = session.scalar(select(tbl.Region).where(tbl.Region.name == nation.region.replace(" ", "_"))).id
                    if not region_id:
                        region_id = None
                    new_user = tbl.User(snowflake=message.author.id)
                    new_nation = tbl.Nation(name=nation.url_name, region_id=region_id)
                    session.add(new_user)
                    session.add(new_nation)
                    session.commit()
                    session.add(tbl.UserNation(user_id=new_user.id, nation_id=new_nation.id))
                    session.commit()

                    guild_db = session.scalar(select(tbl.Guild).where(tbl.Guild.snowflake == origin_guild_id))
                    related = session.scalar(select(tbl.GuildRegion).where(tbl.GuildRegion.region_id == region_id))
                    if not region_id or not related:
                        guild = nerris.get_guild(origin_guild_id)
                        guest_role = guild_db.guest_role
                        member = guild.get_member(message.author.id)
                        role = guild.get_role(guest_role)
                        await member.add_role(role, reason="Verified nation with Nerris!", atomic=True)
                    else:
                        guild = nerris.get_guild()
                        res_role = guild_db.resident_role
                        member = guild.get_member(message.author.id)
                        role = guild.get_role(res_role)
                        await member.add_role(role, reason="Verified nation with Nerris!", atomic=True)

                    del nerris.users_verifying[message.author]
            else:
                await message.author.send("Oh no, looks like I rolled a Nat 1! I can't verify that nation, maybe try again?")


@nerris.hybrid_command()
@commands.is_owner()
async def source(ctx):
    await ctx.send("You can find my source code here! {}".format(Nerris.SOURCE))

@nerris.hybrid_command()
async def info(ctx):
    info_string = (
        "I'm Nerris Version {}!\n"
        "I am a bot created for The Campfire discord server and the associated NS region Sun's Reach!\n"
        "I mostly just help manage nation verification at this time.\n"
        "Now where did my D20 go..."
    ).format(Nerris.__VERSION__)
    await ctx.send(info_string)

@nerris.hybrid_command()
@commands.is_owner()
async def sync(ctx):
    await nerris.tree.sync(guild=ctx.guild)
    await ctx.send("Synced Slash Commands to Server!")


@nerris.hybrid_command()
@commands.is_owner()
@commands.guild_only()
async def link_region(ctx, region_name, verified_role: Optional[discord.Role], resident_role: Optional[discord.Role]):
    with Session(nerris.db_engine) as session:
        new_region = tbl.Region(name=region_name.replace(" ", "_"))
        new_guild = tbl.Guild(snowflake=str(ctx.guild.id))
        session.add(new_region)
        session.add(new_guild)
        session.commit()
        new_association = tbl.GuildRegion(guild_id=new_guild.id, region_id=new_region.id)
        session.add(new_association)
        session.commit()

    try:
        nerris.link_roles(verified_role, resident_role, ctx.message)
    except NoRoles:
        await ctx.send("The region has been registered to this server!")
    except NoGuild as Guild:
        await ctx.send("I was unable to assign to this guild somehow...")
    except InvalidRole as Role:
        await ctx.send("The role {} does not exist somehow".format(Role))
    except NoMeaning as Meaning:
        await ctx.send("Whoops")


@nerris.hybrid_command()
@commands.is_owner()
@commands.guild_only()
async def link_roles(ctx, verified_role: Optional[discord.Role], resident_role: Optional[discord.Role]):
    try:
        await ctx.send(nerris._link_roles(verified_role, resident_role, ctx.message))
    except NoRoles:
        await ctx.send("I don't know why you're trying to add roles without giving me any...")
    except NoGuild as Guild:
        await ctx.send("Looks like you don't have a region associated with this server!")
    except InvalidRole as Role:
        await ctx.send("Oh no, I rolled a Nat 1! I can't currently add that role!")
    except NoMeaning as Meaning:
        await ctx.send("Oh no, I've lost my notes! I can't currently add roles!")


nerris.run(os.environ.get("NERRIS_TOKEN"))
