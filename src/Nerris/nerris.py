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
from Nerris.nationstates.region import Region
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
            if (meanings := session.scalars(select(tbl.Meaning)).all()):
                self.meaning_ids[RoleTypes.VERIFIED.value] = [m.id for m in meanings if m.meaning.casefold() == RoleTypes.VERIFIED.value.casefold()][0]
                self.meaning_ids[RoleTypes.RESIDENT.value] = [m.id for m in meanings if m.meaning.casefold() == RoleTypes.RESIDENT.value.casefold()][0]
                return

            verified_role = tbl.Meaning(meaning=RoleTypes.VERIFIED.value)
            resident_role = tbl.Meaning(meaning=RoleTypes.RESIDENT.value)
            session.add(verified_role)
            session.add(resident_role)
            session.commit()
            self.meaning_ids[RoleTypes.VERIFIED.value] = verified_role.id
            self.meaning_ids[RoleTypes.RESIDENT.value] = resident_role.id

    def store_role(self, session: Session, role: discord.Role, guild: discord.Guild) -> Self:
        guild_db = session.scalar(select(tbl.Guild).where(tbl.Guild.snowflake == guild.id))
        if not guild_db:
            raise InvalidGuild(guild)

        new_role = tbl.Role(snowflake = role.id, guild_id=guild_db.id, guild=guild_db)
        session.add(new_role)
        session.commit() #flush?
        return self

    def remove_role(self, session: Session, role: discord.Role) -> Optional[discord.Role]:
        if (role_db := session.scalar(select(tbl.Role).where(tbl.Role.snowflake == role.id))) is not None:
            session.delete(role_db)
            return role
        return None

    def add_role_meaning(self, session: Session, role: discord.Role, guild: discord.Guild, meaning: RoleTypes) -> Self:
        if meaning.value not in self.meaning_ids:
            raise InvalidMeaning(meaning)

        guild_db = session.scalar(select(tbl.Guild).where(tbl.Guild.snowflake == guild.id))
        if not guild_db:
            raise InvalidGuild(guild)

        if role.id not in [r.snowflake for r in guild_db.roles]:
            raise InvalidRole(role)

        role = [r for r in guild_db.roles if r.snowflake == role.id][0]
        meaning = session.scalar(select(tbl.Meaning).where(tbl.Meaning.id == self.meaning_ids[meaning.value]))
        role.meanings.add(meaning)
        session.commit() #flush?
        return self

    async def verify_nation(self, nation: str, code: Optional[str]) -> tuple[str, Nation]:
        if code is None:
            raise NoCode_NSVerify()

        response, nation = await self.ns_client.verify(nation, code)
        if not response:
            raise InvalidCode_NSVerify(code)

        return "You're verified! Let me put this charactersheet in my campaign binder.", nation

    async def register_nation(self, nation: Nation, message: discord.Message) -> str:
        with Session(self.db_engine) as session:
            region_id = session.scalar(select(tbl.Region.id).where(tbl.Region.name == nation.region))
            if region_id is None:
                new_region = tbl.Region(name=nation.region)
                session.add(new_region)
                session.commit()
                region_id = new_region.id

            new_user = tbl.User(snowflake=message.author.id)
            new_nation = tbl.Nation(name=nation.name, region_id=region_id, users={new_user})
            session.add_all([new_user, new_nation])

            session.commit()
            return "There we go! I'll see if I can get you some roles..."

    async def give_verified_roles_one_guild(self, user: discord.User | discord.Member, guild: discord.Guild, noNationError=True):
        with Session(self.db_engine) as session:
            if isinstance(user, discord.User) or user.guild != guild:
                user = guild.fetch_member(user.id)

            if not user:
                raise NotInGuild()

            guild_db = session.scalar(select(tbl.Guild).where(tbl.Guild.snowflake == guild.id))
            if not guild_db:
                raise InvalidGuild()

            if not guild_db.roles:
                raise NoRoles()

            user_db = session.scalar(select(tbl.User).where(tbl.User.snowflake == user.id))
            if not user_db.nations and noNationError:
                raise NoNation()

            if not guild_db.roles:
                raise NoRoles()

            shared_regions = guild_db.regions & {n.region for n in user_db.nations}

            resident_role_sql = (select(tbl.Role)
                                 .where(tbl.Role.guild_id == guild_db.id)
                                 .join(tbl.RoleMeaning)
                                 .join(tbl.Meaning)
                                 .where(tbl.Meaning.meaning == RoleTypes.RESIDENT.value.casefold())
                                 .distinct())

            verified_role_sql = (select(tbl.Role)
                                 .where(tbl.Role.guild_id == guild_db.id)
                                 .join(tbl.RoleMeaning)
                                 .join(tbl.Meaning)
                                 .where(tbl.Meaning.meaning == RoleTypes.VERIFIED.value.casefold())
                                 .distinct())

            resident_role = session.scalar(resident_role_sql)
            verified_role = session.scalar(verified_role_sql)

            if user_db.nations:
                if resident_role and verified_role:
                    if user.get_role(resident_role.snowflake) and not shared_regions:
                        await user.remove_roles(discord.Object(resident_role.snowflake))
                        await user.add_roles(discord.Object(verified_role.snowflake))
                    elif user.get_role(verified_role.snowflake) and shared_regions:
                        await user.remove_roles(discord.Object(verified_role.snowflake))
                        await user.add_roles(discord.Object(resident_role.snowflake))
                    else:
                        await user.add_roles(discord.Object(verified_role.snowflake))
                elif resident_role:
                    has_role = user.get_role(resident_role.snowflake)
                    if not has_role and shared_regions:
                        await user.add_roles(discord.Object(resident_role.snowflake))
                    elif has_role and not shared_regions:
                        await user.remove_roles(discord.Object(resident_role.snowflake))
                elif verified_role:
                    if user.get_role(verified_role.snowflake):
                        await user.add_roles(discord.Object(verified_role.snowflake))
            else:
                if resident_role and verified_role:
                    if user.get_role(resident_role.snowflake):
                        await user.remove_roles(discord.Object(resident_role.snowflake))
                    if user.get_role(verified_role.snowflake):
                        await user.remove_roles(discord.Object(verified_role.snowflake))
                elif resident_role:
                    has_role = user.get_role(resident_role.snowflake)
                    if user.get_role(resident_role.snowflake):
                        await user.remove_roles(discord.Object(resident_role.snowflake))
                elif verified_role:
                    if user.get_role(verified_role.snowflake):
                        await user.remove_roles(discord.Object(verified_role.snowflake))

    async def update_verified_roles(self, user: discord.User | discord.Member):
        with Session(self.db_engine) as session:
            if not session.scalars(select(tbl.Role)).all():
                raise NoRoles()

            mutual_guilds = {g.id:(g, m) for g in self.guilds if (m := await g.fetch_member(user.id))}

            active_guilds = session.scalars(select(tbl.Guild.snowflake).where(tbl.Guild.snowflake.in_(mutual_guilds.keys()))).all()
            if not active_guilds:
                raise NoGuilds()

            for guild_snowflake in active_guilds:
                try:
                    await self.give_verified_roles_one_guild(mutual_guilds[guild_snowflake][1], mutual_guilds[guild_snowflake][0], noNationError=False)
                except NotInGuild:
                    pass


    async def give_verified_roles(self, user: discord.User | discord.Member):
        with Session(self.db_engine) as session:
            if not session.scalars(select(tbl.Role)).all():
                raise NoRoles()

            mutual_guilds = {g.id:(g, m) for g in self.guilds if (m := await g.fetch_member(user.id))}

            active_guilds = session.scalars(select(tbl.Guild.snowflake).where(tbl.Guild.snowflake.in_(mutual_guilds.keys()))).all()
            if not active_guilds:
                raise NoGuilds()

            for guild_snowflake in active_guilds:
                try:
                    await self.give_verified_roles_one_guild(mutual_guilds[guild_snowflake][1], mutual_guilds[guild_snowflake][0])
                except NotInGuild:
                    pass

    def link_roles(self, verified_role: Optional[discord.Role], resident_role: Optional[discord.Role], message: discord.Message, override: Optional[bool] = False) -> str:
        with Session(self.db_engine) as session:
            if verified_role is None and resident_role is None:
                raise NoRoles()

            guild_id = session.scalar(select(tbl.Guild.id).where(tbl.Guild.snowflake == message.guild.id))
            verified_sql = (select(tbl.Role)
                            .where(tbl.Role.guild_id == guild_id)
                            .join(tbl.RoleMeaning)
                            .join(tbl.Meaning)
                            .where(tbl.Meaning.meaning == RoleTypes.VERIFIED.value.casefold())
                            .distinct())
            resident_sql = (select(tbl.Role)
                            .where(tbl.Role.guild_id == guild_id)
                            .join(tbl.RoleMeaning)
                            .join(tbl.Meaning)
                            .where(tbl.Meaning.meaning == RoleTypes.RESIDENT.value.casefold())
                            .distinct())

            if verified_role is not None:
                role = session.scalar(verified_sql)
                if role and override:
                    session.delete(role)
                    session.commit()
                elif not role:
                    nerris.store_role(session, verified_role, message.guild).add_role_meaning(session, verified_role, message.guild, RoleTypes.VERIFIED)
                else:
                    raise RoleOverwrite(verified_role)


            if resident_role is not None:
                role = session.scalar(resident_sql)
                if role and override:
                    session.delete(role)
                    session.commit()
                elif not role:
                    nerris.store_role(session, resident_role, message.guild).add_role_meaning(session, resident_role, message.guild, RoleTypes.RESIDENT)
                else:
                    raise RoleOverwrite(resident_role)

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
        user_nations = session.scalar(select(tbl.User.nations).where(tbl.User.snowflake == ctx.message.author.id))
        if user_nations:
            await ctx.send('\n'.join(user_nations), ephemeral=private_response)
    await ctx.send("I don't have any nations for you!")

@nerris.listen('on_member_join')
async def verify_on_join(member: discord.Member):
    with Session(nerris.db_engine) as session:
        await nerris.give_verified_roles_one_guild(member, member.guild)


@nerris.listen('on_guild_role_delete')
async def remove_stored_roles(role: discord.Role):
    with Session(nerris.db_engine) as session:
        role_db = session.scalar(select(tbl.Role).where(tbl.Role.snowflake == role.id))
        if role_db:
            session.delete(role_db)
            session.commit()


@nerris.listen('on_guild_role_update')
async def update_stored_roles(before: discord.Role, after: discord.Role):
    with Session(nerris.db_engine) as session:
        role_db = session.scalar(select(tbl.Role).where(tbl.Role.snowflake == before.id))
        if before.id != after.id and role_db:
            role_db.snowflake = after.id
            session.commit()


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
    region = await nerris.ns_client.get_region(region_name)
    with Session(nerris.db_engine) as session:
        new_region = tbl.Region(name=region.name)
        new_guild = tbl.Guild(snowflake=ctx.guild.id, regions={new_region})
        session.add_all([new_region, new_guild])
        session.commit() #flush?

    try:
        nerris.link_roles(verified_role, resident_role, ctx.message, override=False)
        await ctx.send("The region has been registered to this server along with the roles!")

        with Session(nerris.db_engine) as session:
            users = session.scalars(select(tbl.User.snowflake)).all()
            if users:
                members = await ctx.guild.query_members(user_ids=users)
                for member in members:
                    await nerris.give_verified_roles_one_guild(member, ctx.guild)

    except NoRoles:
        await ctx.send("I don't know why you're trying to add roles without giving me any...")
    except InvalidGuild as Guild:
        await ctx.send("Looks like you don't have a region associated with this server!")
    except InvalidRole as Role:
        await ctx.send("Oh no, I rolled a Nat 1! I can't currently add that role!")
    except InvalidMeaning as Meaning:
        await ctx.send("Oh no, I've lost my notes! I can't currently add roles!")
    except RoleOverwrite as Role:
        await ctx.send("Unfortuantely that would overwrite a role. Use `\link_roles` with overrwrite_roles set to True")

@nerris.hybrid_command()
@commands.is_owner()
@commands.guild_only()
async def link_roles(ctx, verified_role: Optional[discord.Role], resident_role: Optional[discord.Role], overwrite_roles: Optional[bool] = False):
    try:
        await ctx.send(nerris.link_roles(verified_role, resident_role, ctx.message, override=overwrite_roles))

        with Session(nerris.db_engine) as session:
            users = session.scalars(select(tbl.User.snowflake)).all()
            if users:
                members = await ctx.guild.query_members(user_ids=users)
                for member in members:
                    await nerris.give_verified_roles_one_guild(member, ctx.guild)

    except NoRoles:
        await ctx.send("I don't know why you're trying to add roles without giving me any...")
    except InvalidGuild as Guild:
        await ctx.send("Looks like you don't have a region associated with this server!")
    except InvalidRole as Role:
        await ctx.send("Oh no, I rolled a Nat 1! I can't currently add that role!")
    except InvalidMeaning as Meaning:
        await ctx.send("Oh no, I've lost my notes! I can't currently add roles!")
    except RoleOverwrite as Role:
        await ctx.send("Unfortuantely that would overwrite a role. Use `\link_roles` with overrwrite_roles set to True")


@nerris.hybrid_command()
@commands.is_owner()
@commands.guild_only()
async def unlink_roles(ctx, verified_role: Optional[discord.Role], resident_role: Optional[discord.Role], remove_roles: Optional[bool] = True):
    unlinked_roles: list[discord.Role] = []
    with Session(nerris.db_engine) as session:
        if verified_role and (res := nerris.remove_role(session, verified_role)) is not None:
            unlinked_roles.append(res)
        if resident_role and (res := nerris.remove_role(session, resident_role)) is not None:
            unlinked_roles.append(res)
        session.commit()

    if remove_roles:
        for role in unlinked_roles:
            for member in role.members:
                await member.remove_roles(role)
    if unlinked_roles:
        await ctx.send("I've gone ahead and removed that role from my notes!")
    else:
        await ctx.send("You didn't give me any valid roles to remove from notes!...")


@nerris.hybrid_command()
@commands.is_owner()
@commands.guild_only()
async def unlink_region(ctx, region_name: str):
    with Session(nerris.db_engine) as session:
        ns_region = await nerris.ns_client.get_region(region_name.replace(" ", "_"))
        region = session.scalar(select(tbl.Region).where(tbl.Region.name == ns_region.name))
        guild = session.scalar(select(tbl.Guild).where(tbl.Guild.snowflake == ctx.guild.id))
        if region and region in guild.regions:
            guild.regions.remove(region)

        await ctx.send("I've gone ahead and removed that role from my notes!")

@nerris.hybrid_command()
@commands.guild_only()
async def unverify_nation(ctx, nation_name: str):
    with Session(nerris.db_engine) as session:
        if (user := session.scalar(select(tbl.User).where(tbl.User.snowflake == ctx.author.id))) is not None:
            ns_nation = await nerris.ns_client.get_nation(nation_name)
            if (nation := session.scalar(select(tbl.Nation).where(tbl.Nation.name == ns_nation.name))) is not None:
                if nation in user.nations:
                    try:
                        nation.users.remove(user)
                        user.nations.remove(nation)
                    except (ValueError, KeyError):
                        pass
                    if not nation.users:
                        session.delete(nation)
                    session.commit()
                    await nerris.update_verified_roles(ctx.author)
                    if not user.nations:
                        session.delete(user)
                    session.commit()

    await ctx.send("I've removed your character sheet from my campaign notes.")


nerris.run(os.environ.get("NERRIS_TOKEN"))
