"""
The main module for Nerris.

This contains all the main 'logic' for the Discord Bot part of things.
"""

import asyncio
import os

from typing import Self, Optional

import aiohttp
import discord
from discord.ext import commands

from sqlalchemy.orm import Session
from sqlalchemy import select

import Nerris
from Nerris.database.base import Base
from Nerris.database import tables as tbl
from Nerris.database import db
from Nerris.enums import RoleTypes
from Nerris.nationstates.nation import Nation
from Nerris.nationstates import ns
from Nerris.exceptions import *


intents = discord.Intents.default()

intents.message_content = True
intents.members = True
intents.presences = True

class NerrisBot(commands.Bot):
    """
    The main Discord Bot Class
    """
    db_engine = db.connect(in_memory=True)
    users_verifying = {}
    meaning_ids: dict[RoleTypes, int] = {RoleTypes.VERIFIED.value: None,
                                         RoleTypes.RESIDENT.value: None}

    async def on_ready(self, *args, **kwargs):
        self.aiohttp_session = aiohttp.ClientSession()
        self.ns_client = await ns.NationStatesClient(self.aiohttp_session).build()
        print("We are logged in as {}".format(self.user))
        Base.metadata.create_all(self.db_engine)
        self.register_meanings()
        await self.tree.sync()

    def register_meanings(self):
        with Session(self.db_engine) as session:
            if (meanings := session.scalars(select(tbl.Meanings)).all()):
                self.meaining_ids[RoleTypes.VERIFIED.value] = [m.id for m in meanings if m.meaning.casefold() == RoleTypes.VERIFIED.value.casefold()]
                self.meaining_ids[RoleTypes.RESIDENT.value] = [m.id for m in meanings if m.meaning.casefold() == RoleTypes.RESIDENT.value.casefold()]
                return

            verified_role = tbl.Meaning(meaning=RoleTypes.VERIFIED.value)
            resident_role = tbl.Meaning(meaning=RoleTypes.RESIDENT.value)
            session.add(verified_role)
            session.add(resident_role)
            session.commit()
            self.meaning_ids[RoleTypes.VERIFIED.value] = verified_role.id
            self.meaning_ids[RoleTypes.RESIDENT.value] = resident_role.id

    def store_role(self, session: Session, role: discord.Role, guild: discord.Guild) -> Self:
        guild_id = session.scalar(select(tbl.Guild).where(tbl.Guild.snowflake == guild.id))
        if not guild_id:
            raise InvalidGuild(guild)
        new_role = tbl.Role(snowflake = role.id, guild_id=guild_id.id)
        session.add(new_role)
        session.commit() #flush?
        return self

    def add_role_meaning(self, session: Session, role: discord.Role, guild: discord.Guild, meaning: RoleTypes) -> Self:
        _meaning = session.scalar(select(tbl.Meaning.id).where(tbl.Meaning.meaning == meaning.value))

        if not _meaning:
            raise InvalidMeaning(meaning)
        meaning = _meaning

        _guild = session.scalar(select(tbl.Guild).where(tbl.Guild.snowflake == guild.id))
        if not _guild:
            raise InvalidGuild(guild)
        guild = _guild

        _role = session.scalar(select(tbl.Role).where(tbl.Role.snowflake == role.id and tbl.Role.guild_id == guild.id))
        if not _role:
            raise InvalidRole(role)
        role = _role

        role_meaning = tbl.RoleMeaning(meaning_id = meaning, role_id = role.id)
        session.add(role_meaning)
        session.commit() #flush?
        return self


    @staticmethod
    def store_nation(session: Session, user_id: str, nation: Nation, region_id: int) -> tuple[tbl.User, tbl.Nation]:
        new_user = tbl.User(snowflake=user_id)
        new_nation = tbl.Nation(name=nation.name, url_name=nation.url_name, region_id=region_id)
        session.add(new_user)
        session.add(new_nation)
        session.commit() #flush?
        return new_user, new_nation

    @staticmethod
    def _link_nation_user(session: Session, user_id: int, nation_id: int):
        session.add(tbl.UserNation(user_id=user_id, nation_id=nation_id))
        session.commit() #flush?

    async def verify_nation(self, nation: str, code: Optional[str]) -> tuple[str, Nation]:
        if code is None:
            raise NoCode_NSVerify()

        response, nation = await self.ns_client.verify(nation, code)
        if not response:
            raise InvalidCode_NSVerify(code)

        return "You're verified! Let me put this charactersheet in my campaign binder.", nation

    async def register_nation(self, nation: Nation, message: discord.Message) -> str:
        with Session(self.db_engine) as session:
            region_id = session.scalar(select(tbl.Region.id).where(tbl.Region.url_name == nation.region_url_name))
            if region_id is None:
                new_region = tbl.Region(name=nation.region, url_name=nation.region_url_name)
                session.add(new_region)
                session.commit()
                region_id = new_region.id

            user, nation = self.store_nation(session, message.author.id, nation, region_id)
            self._link_nation_user(session, user.id, nation.id)

            session.commit()
            return "There we go! I'll see if I can get you some roles..."

    async def _get_mutual_guilds(self, user: discord.User | discord.Member) -> tuple[dict, dict]:
        """
        Gets mutual guilds that the bot and the user are in.
        """
        guild_members = [(g, m) for g in self.guilds if (m := await g.fetch_member(user.id))]
        mutual_guilds = {}
        for g in self.guilds:
            member = await g.fetch_member(user.id)
            if member:
                mutual_guilds[g] = member
        return (mutual_guilds, guild_member)

    async def give_verified_roles_one_guild(self, user: discord.User | discord.Member, guild: discord.Guild):
        with Session(self.db_engine) as session:
            if not session.scalars(select(tbl.Role)).all():
                raise NoRoles()


            member = guild.fetch_member(user.id)
            if not member:
                raise NotInGuild()

            guild_db = session.scalar(select(tbl.Guild).where(tbl.Guild.snowflake == guild.id))
            if not guild_db:
                raise InvalidGuild()

            user_id = session.scalar(select(tbl.User.id).where(tbl.User.snowflake == user.id))
            nation_ids = session.scalars(select(tbl.UserNation.nation_id).where(tbl.UserNation.user_id == user_id)).all()
            if not nation_ids:
                raise NoNation()

            roles = session.scalars(select(tbl.Role).where(tbl.Role.guild_id == guild_db.id())).all()
            if not roles:
                raise NoRoles()

            role = roles[0]
            # Assume we are correct at first.
            if len(roles) == 2 or session.scalar(select(tbl.RoleMeaning).where(tbl.RoleMeaning.role_id == roles[0],
                                                                               tbl.RoleMeaning.meaning_id == self.meaning_ids[RoleTypes.RESIDENT.value])):
                # We need to determine residency
                residing_region_ids = session.scalars(select(select.tbl.Nation.region_id).where(tbl.nation_id.in_(nation_ids))).all()
                region_ids = session.scalars(select(tbl.GuildRegion.region_id).where(tbl.GuildRegion.guild_id == guild_db.id,
                                                                                     tbl.GuildRegion.region_id.in_(residing_region_ids))).all()
                if region_ids:
                    role = [r for r in roles if r.meaning.casefold() == RoleTypes.RESIDENT.value.casefold()][0]
                else if len(roles) == 2:
                    role = [r for r in roles if r.meaning.casefold() == RoleTypes.VERIFIED.value.casefold()][0]
                member = mutual_guilds[guild]
            
            await member.add_roles(discord.Object(role.snowflake))

    async def give_verified_roles(self, user: discord.User | discord.Member):
        with Session(self.db_engine) as session:
            if not session.scalars(select(tbl.Role)).all():
                raise NoRoles()

            mutual_guilds, guild_member = self._get_mutual_guilds(user)

            active_guilds = session.scalars(select(tbl.Guild).where(tbl.Guild.snowflake.in_([g.id for g in mutual_guilds.keys()]))).all()
            if not active_guilds:
                raise NoGuilds()

            user_id = session.scalar(select(tbl.User.id).where(tbl.User.snowflake == user.id))
            nation_ids = session.scalars(select(tbl.UserNation.nation_id).where(tbl.UserNation.user_id == user_id)).all()
            if not nation_ids:
                raise NoNation


            elligble_roles = {'verified': {}, 'resident':{}}

            meaning_id = session.scalar(select(tbl.Meaning.id).where(tbl.Meaning.meaning == RoleTypes.VERIFIED.value))
            if not meaning_id:
                raise InvalidMeaning(RoleTypes.VERIFIED.value)

            verified_role_ids = session.scalars(select(tbl.RoleMeaning.role_id).where(tbl.RoleMeaning.meaning_id == meaning_id)
                                               ).all()

            verified  = session.scalars(select(tbl.Role
                                              ).where(tbl.Role.id.in_(verified_role_ids),
                                                      tbl.Role.guild_id.in_([g.id for g in active_guilds]))).all()

            elligble_roles['verified'] = {[g.snowflake for g in active_guilds if g.id == r.guild_id][0]: r for r in verified}

            meaning_id = None

            meaning_id = session.scalar(select(tbl.Meaning.id).where(tbl.Meaning.meaning == RoleTypes.RESIDENT.value))
            if meaning_id:
                region_ids = session.scalars(select(tbl.Nation.region_id).where(tbl.Nation.id.in_(nation_ids))).all()

                resident_role_ids = session.scalars(select(tbl.RoleMeaning.role_id).where(tbl.RoleMeaning.meaning_id == meaning_id)).all()
                resident_guild_regions = session.scalars(select(tbl.GuildRegion.guild_id).where(tbl.GuildRegion.guild_id.in_([g.id for g in active_guilds]),
                                                                       tbl.GuildRegion.region_id.in_(region_ids))).all()

                resident = session.scalars(select(tbl.Role).where(tbl.Role.id.in_(resident_role_ids),
                                                                  tbl.Role.guild_id.in_(resident_guild_regions))).all()


                guilds = session.scalars(select(tbl.Guild).where(tbl.Guild.id.in_(resident_guild_regions))).all()
                elligble_roles['resident'] = {[g.snowflake for g in guilds if g.id == r.guild_id][0]: r for r in resident}

                for guild in elligble_roles['resident']:
                    if guild in elligble_roles['verified']:
                        del elligble_roles['verified'][guild]

            roles = {g: elligble_roles[k][g] for k in elligble_roles for g in elligble_roles[k]}
            for guild in mutual_guilds:
                member = mutual_guilds[guild]
                await member.add_roles(discord.Object(roles[str(guild.id)].snowflake))


    def _link_roles(self, verified_role: Optional[discord.Role], resident_role: Optional[discord.Role], message: discord.Message) -> str:
        with Session(self.db_engine) as session:
            if verified_role is None and resident_role is None:
                raise NoRoles()

            if verified_role is not None:
                nerris.store_role(session, verified_role, message.guild).add_role_meaning(session, verified_role, message.guild, RoleTypes.VERIFIED)

            if resident_role is not None:
                nerris.store_role(session, resident_role, message.guild).add_role_meaning(session, resident_role, message.guild, RoleTypes.RESIDENT)

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
async def verified_nations(ctx, private_response: Optional[bool] = True):
    """
    Displays Verified Nations of a given user.
    """
    with Session(nerris.db_engine) as session:
        user_id = session.scalar(select(tbl.User.id).where(tbl.User.snowflake == ctx.message.author.id))
        if user_id:
            nation_ids = session.scalars(select(tbl.UserNation.nation_id).where(tbl.UserNation.user_id == user_id)).all()
            if nation_ids:
                nations = session.scalars(select(tbl.Nation.name).where(tbl.Nation.id.in_(nation_ids))).all()
                await ctx.send('\n'.join(nations), ephemeral=private_response)
    await ctx.send("I don't have any nations for you!")

@nerris.listen('on_member_join')
async def verify_on_join(member):
    with Session(nerris.db_engine) as session:
        await nerris.give_verified_roles_one_guild(member, member.guild)


@nerris.hybrid_command()
@commands.guild_only()
async def verify_nation(ctx, code: Optional[str], nation: str):
    """
    Verifies a nation and assigns it to a user.
    """
    with Session(nerris.db_engine) as session:
        if session.scalars(select(tbl.Nation).where(tbl.Nation.name == nation.replace(" ", "_"))).all():
            await ctx.send("That nation has a character sheet already, silly!", ephemeral=True)
            return

    if code is None:
        await ctx.send("Alrighty! Please check your DMs", ephemeral=True)
        message = await ctx.message.author.send(("Hi please log into your {} now. After doing so go to this link: {}\n"
                                       "Copy the code from that page and paste it here.\n"
                                       "**__This code does not give anyone access to your nation or any control over it. It only allows me to verify identity__**\n"
                                       "Pretty cool, huh?").format(nation, nerris.ns_client.get_verify_url()))
        nerris.users_verifying[ctx.message.author.name] = (nation, message)

        await asyncio.sleep(60)
        if ctx.message.author in nerris.users_verifying:
            await ctx.message.author.send(("Oh, you didn't want to verify? That's fine. If you change your mind just `/verify_nation` again!"))
            del nerris.users_verifying[ctx.message.author.name]
    else:
        message = None
        try:
            async with ctx.typing(ephemeral=True):
                res, nation = await nerris.verify_nation(nation, code)
                message = await ctx.send("Thanks for the character sheet! I'll go ahead and put you in my campaign binder...", ephemeral=True)

            res = await nerris.register_nation(nation, ctx.message)
            await message.edit(content="There we go! I'll give you roles now...")

            await nerris.give_verified_roles(ctx.message.author)
            await message.edit(content="Done! I've given you all roles you can have!")
        except InvalidCode_NSVerify as code:
            await ctx.send("Oh no, you didn't role high enough it seems. {} isn't the right code!".format(code.args[0]), ephemeral=True)
        except (NoGuilds, NoRoles, NoMeanings, NoNation, NoCode_NSVerify):
            await ctx.send("There was an internal error...", ephemeral=True)
            raise


@nerris.listen('on_message')
async def _verify_nation(message):
    if message.guild is None and message.author.name in nerris.users_verifying:
        (nation, _message) = nerris.users_verifying[message.author.name]
        try:
            async with message.channel.typing():
                res, nation = await nerris.verify_nation(nation, message.content)
            await _message.edit(content=res)

            async with message.channel.typing():
                res = await nerris.register_nation(nation, message)
            await _message.edit(content=res)

            async with message.channel.typing():
                del nerris.users_verifying[message.author.name]
                await nerris.give_verified_roles(message.author)
            await _message.edit(content="I've given you roles in all servers I can!")
        except NoCode_NSVerify:
            await _message.edit(content="You need to give me the code")
        except InvalidCode_NSVerify as Code:
            await _message.edit(content="Hmm...{} isn't right. Maybe cast scry and you'll find the right one...".format(Code.args[0]))
        except (NoGuilds, NoRoles):
            await _message.edit(content="I can't give you any roles right now. Thanks for the charactersheet though!")
        except NoMeanings:
            await _message.edit(content="Oh...I don't think I have a roles I can give for that...")
        except NoNation as Nation:
            await _message.edit(content="Oh I don't have the charactersheet for {}...".format(Nation.args[0].name))

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
async def link_region(ctx, region_name: str, verified_role: Optional[discord.Role], resident_role: Optional[discord.Role]):
    with Session(nerris.db_engine) as session:
        new_region = tbl.Region(name=region_name, url_name=region_name.replace(" ", "_").casefold())
        new_guild = tbl.Guild(snowflake=str(ctx.guild.id))
        session.add(new_region)
        session.add(new_guild)
        session.commit() #flush?
        new_association = tbl.GuildRegion(guild_id=new_guild.id, region_id=new_region.id)
        session.add(new_association)
        session.commit()

    try:
        nerris._link_roles(verified_role, resident_role, ctx.message)
        await ctx.send("The region has been registered to this server along with the roles!")
    except NoRoles:
        await ctx.send("The region has been registered to this server!")
    except InvalidGuild as Guild:
        await ctx.send("I was unable to assign to this guild somehow...")
    except InvalidRole as Role:
        await ctx.send("The role {} does not exist somehow".format(Role))
    except InvalidMeaning as Meaning:
        await ctx.send("Whoops")

@nerris.hybrid_command()
@commands.is_owner()
@commands.guild_only()
async def link_roles(ctx, verified_role: Optional[discord.Role], resident_role: Optional[discord.Role]):
    try:
        await ctx.send(nerris._link_roles(verified_role, resident_role, ctx.message))
    except NoRoles:
        await ctx.send("I don't know why you're trying to add roles without giving me any...")
    except InvalidGuild as Guild:
        await ctx.send("Looks like you don't have a region associated with this server!")
    except InvalidRole as Role:
        await ctx.send("Oh no, I rolled a Nat 1! I can't currently add that role!")
    except InvalidMeaning as Meaning:
        await ctx.send("Oh no, I've lost my notes! I can't currently add roles!")


nerris.run(os.environ.get("NERRIS_TOKEN"))
