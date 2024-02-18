"""
This module contains all the stuff for NSVerify Functionality.
"""
import asyncio
import datetime
import logging
from typing import Optional, Any

import discord
from discord.ext import commands, tasks
from sqlalchemy import select
from sqlalchemy.orm import Session

import Scout.exceptions
from Scout.database import db, models
import Scout.nsapi.ns as ns
from Scout.core.nationstates import __VERSION__
from Scout.database.models import Region, User, Nation, user_nation

VERIFIED = "NSVerify:user-verified"
RESIDENT = "NSVerify:user-resident"

utc = datetime.timezone.utc
time = datetime.time(hour=8, minute=00, tzinfo=utc)
logger = logging.getLogger("discord.cogs.core.nationstates.nsverify")


class NSVerify(commands.Cog):
    """A cog that provides the NSVerify functionality for Nerris.

    Attributes:
        ns_client: The ns_client used for ns-api queries.
        users_verifying: The users currently attempting to verify themselves.
    """
    ns_client: ns.NationStates_Client
    user_agent: Optional[str]
    users_verifying: dict[Any, Any] = {}

    def __init__(self, bot, ns_client):
        """Initalizes the cog.

        Args:
            bot: The DiscordBot object.
        """
        self.scout = bot
        self.scout.register_association(VERIFIED)
        self.scout.register_association(RESIDENT)
        self.update_nations.start()
        self.ns_client = ns_client

    # @tasks.loop(time=time)
    @tasks.loop(count=1)
    async def update_nations(self):
        """Handle the automatic update of nations.
        """
        with Session(self.scout.engine) as session:
            for user in self.scout.get_all_members():
                if session.scalar(select(User).where(User.snowflake == user.id).join(user_nation)) is not None:
                    await self.give_verified_roles(user, None, session=session)

    async def cog_load(self):
        """The function that the bot runs when the Cog is loaded.
        """
        user_agent = ns.create_user_agent(self.scout.config["CONTACT_INFO"],
                                          self.scout.config["NATION"],
                                          self.scout.config["REGION"])
        self.user_agent = "NSVerify-Cog/{} {}".format(__VERSION__, user_agent)

    async def cog_unload(self) -> None:
        """Things to do when the cog is unloaded/at bot shutdown.
        """
        self.update_nations.stop()

    def _link_roles(self, verified_role: Optional[discord.Role], resident_role: Optional[discord.Role],
                    guild: discord.Guild, overwrite: Optional[bool] = False) -> str:
        """Links the discord roles to the actual association for a server.

        Args:
            verified_role: The role to use as the basic verified role, if not included a verified role will not be added.
            resident_role: The role to use as the role for residents in the server's region.
                If not included, it will not be added.

            guild: The discord guild this all applies to.
            overwrite: If set to true, then the bot will overwrite existing verified and/or resident roles setup
                with the bot.

        Returns:
            Returns a success message for the bot to send.

        Raises:
            Scout.exceptions.NoRoles: No roles were given to the bot.
        """
        if verified_role is None and resident_role is None:
            raise Scout.exceptions.NoRoles()

        with Session(self.scout.engine) as session:
            guild = session.scalar(select(models.Guild).where(models.Guild.snowflake == guild.id))
            # noinspection DuplicatedCode
            if resident_role is not None:
                association = session.scalar(select(models.Association)
                                             .where(models.Association.id == self.scout.associations[RESIDENT]))

                role = models.Role(snowflake=resident_role.id, guild_id=guild.id)

                associated_role = session.scalar(select(models.Role)
                                                 .join(models.role_associations)
                                                 .join(models.Association)
                                                 .where(models.Association.id == self.scout.associations[RESIDENT])
                                                 .where(models.Role.guild_id == guild.id))

                if associated_role is not None and not overwrite:
                    raise Scout.exceptions.RoleOverwrite()
                elif associated_role is not None and overwrite:
                    role.associations.add(association)
                    session.delete(associated_role)
                    session.add(role)
                else:
                    role.associations.add(association)
                    session.add(role)
            # noinspection DuplicatedCode
            if verified_role is not None:
                association = session.scalar(select(models.Association)
                                             .where(models.Association.id == self.scout.associations[VERIFIED]))

                role = models.Role(snowflake=verified_role.id, guild_id=guild.id)

                associated_role = session.scalar(select(models.Role)
                                                 .join(models.role_associations)
                                                 .join(models.Association)
                                                 .where(models.Association.id == self.scout.associations[VERIFIED])
                                                 .where(models.Role.guild_id == guild.id))

                if associated_role is not None and not overwrite:
                    raise Scout.exceptions.RoleOverwrite()
                elif associated_role is not None and overwrite:
                    role.associations.add(association)
                    session.delete(associated_role)
                    session.add(role)
                else:
                    role.associations.add(association)
                    session.add(role)

            session.commit()
        if verified_role is not None and resident_role is not None:
            return ("A Natural 20, a critical success! I've obtained the mythical +1 roles of {} and {}!"
                    ).format(verified_role.name, resident_role.name)
        if verified_role is not None:
            return ("Looks like I found the mythical role of {}...now to find the other piece."
                    ).format(verified_role)
        return ("Looks like I found the mythical role of {}...now to find the other piece."
                ).format(resident_role)

    @commands.hybrid_command()  # type: ignore
    @commands.check_any(commands.has_guild_permissions(administrator=True), commands.is_owner())
    @commands.guild_only()
    async def link_region(self, ctx, region_name: str, verified_role: Optional[discord.Role],
                          resident_role: Optional[discord.Role]):
        """The command that links the discord server and NationStates Region together.

        If no roles are given, it only links the server and region together.

        Parameters:
            ctx: The message context.
            region_name: The name of the ns region to use.

            verified_role: The discord role to use as the verified with the bot role.
            resident_role: The discord role to use as the resident bot role.
        """
        with Session(self.scout.engine) as session:
            region = session.scalar(select(Region).where(Region.name == region_name.casefold()))
            new_guild = session.scalar(select(models.Guild).where(models.Guild.snowflake == ctx.guild.id))
            if new_guild is None:
                new_guild = models.Guild(snowflake=ctx.guild.id)
                session.add(new_guild)
            if region not in new_guild.regions:
                new_guild.regions.add(region)
            session.commit()  # flush?

            try:
                self._link_roles(verified_role, resident_role, ctx.guild)
                await ctx.send("The region has been registered to this server along with the roles!")

                users = session.scalars(select(User.snowflake)).all()
                if users:
                    members = await ctx.guild.query_members(user_ids=users)
                    for member in members:
                        await self.give_verified_roles(member, ctx.guild, session=session)

            except Scout.exceptions.NoRoles:
                await ctx.send("I've added that world to my maps!")
            except Scout.exceptions.InvalidGuild:
                await ctx.send("Looks like you don't have a region associated with this server!")
            except Scout.exceptions.InvalidRole:
                await ctx.send("Oh no, I rolled a Nat 1! I can't currently add that role!")
            except Scout.exceptions.InvalidAssociation:
                await ctx.send("Oh no, I've lost my notes! I can't currently add roles!")
            except Scout.exceptions.RoleOverwrite:
                await ctx.send(
                    "Unfortunately that would overwrite a role. Use `\\link_roles` with overwrite_roles set to True")

    @commands.hybrid_command()  # type: ignore
    @commands.check_any(commands.has_guild_permissions(administrator=True), commands.is_owner())
    @commands.guild_only()
    async def unlink_region(self, ctx, region_name: str):
        """Unlink a region from a Discord server.


        Parameters:
            ctx: The message context
            region_name: The name of the region to unlink from the server.
        """
        with Session(self.scout.engine) as session:
            region = db.get_region(region_name.casefold(), session=session)
            guild = db.get_guild(ctx.guild.id, session=session)

            if region is not None and guild is not None:
                if region in guild.regions:
                    guild.regions.remove(region)
                    session.commit()
                    return await ctx.send("I've removed this region from my maps!")
                return await ctx.send("I couldn't find that region...")
            await ctx.send("I couldn't find that region or guild...")

    async def verify_dm_flow(self, ctx, nation: str):
        """This handles the verification flow in Direct Messages.

        Parameters:
            ctx: The original verification command message context
            nation: The nation to use for this.
        """
        await ctx.send("Alrighty! Please check your DMs", ephemeral=True)
        message = await ctx.message.author.send(
            ("Hi please log into your {} now. After doing so go to this link: "
             "https://nationstates.net/page=verify_login\n"
             "Copy the code from that page and paste it here.\n"
             "**__This code does not give anyone access to your nation or any control over it. It only allows me "
             "to verify identity__**\n"
             "Pretty cool, huh?").format(nation))
        self.users_verifying[ctx.message.author.name] = (nation, message)

        await asyncio.sleep(60)
        if ctx.message.author in self.users_verifying:
            await ctx.message.author.send((
                "Oh, you didn't want to verify? That's fine. If you change your mind just `/verify_nation` again!"))
            del self.users_verifying[ctx.message.author.name]

    @commands.hybrid_command()  # type: ignore
    @commands.guild_only()
    async def verify_nation(self, ctx, code: Optional[str], nation: str):
        """ The discord command to verify a nation and add it to a user.

        Parameters:
            ctx: The message context for the command.
            code: If you know what you are doing you can provide the NS Verification Code to directly verify with one command.
            nation: The name of the nation you are verifying with.
        """
        with Session(self.scout.engine) as session:
            if db.get_nation(nation, session=session):
                await ctx.send("That nation has a character sheet already, silly!", ephemeral=True)
                return

        if code is None:
            await self.verify_dm_flow(ctx, nation)
        else:
            try:
                message = None
                async with ctx.typing(ephemeral=True):
                    res, ns_nation = await self._verify_nation(nation, code)
                    if res:
                        message = await ctx.send(
                            "Thanks for the character sheet! I'll go ahead and put you in my campaign binder...",
                            ephemeral=True)
                    else:
                        message = await ctx.send(
                            ("That's not quite right...The code is: `{}` and the nation is: `{}`...right?"
                             ).format(code, ns_nation.name),
                            ephemeral=True)

                with Session(self.scout.engine) as session:
                    await self.register_nation(ns_nation, ctx.message, session=session)
                    await message.edit(content="There we go! I'll give you roles now...")

                    await self.give_verified_roles(ctx.message.author, session=session)
                    await message.edit(content="Done! I've given you all roles you can have!")
            except Scout.exceptions.InvalidCode_NSVerify:
                await ctx.send("Oh no, you didn't role high enough it seems. `{}` isn't the right code!".format(code),
                               ephemeral=True)
            except (Scout.exceptions.NoGuilds, Scout.exceptions.NoRoles, Scout.exceptions.NoAssociations,
                    Scout.exceptions.NoNation, Scout.exceptions.NoCode_NSVerify):
                await ctx.send("There was an internal error...", ephemeral=True)
                raise

    @commands.Cog.listener('on_message')
    async def verify_nation_msg(self, message):
        """An on_message listener to actually handle the DM verification portion of Verification.

        Arguments:
            message: The discord message that triggered this.
        """
        if message.guild is not None or message.author.name not in self.users_verifying:
            return
        (nation, _message) = self.users_verifying[message.author.name]
        try:
            async with message.channel.typing():
                res, nation = await self._verify_nation(nation, message.content)
            await _message.edit(content=res)

            async with message.channel.typing():
                with Session(self.scout.engine) as session:
                    res = await self.register_nation(nation, message, session=session)
            await _message.edit(content=res)

            async with message.channel.typing():
                del self.users_verifying[message.author.name]
                await self.give_verified_roles(message.author)
            await _message.edit(content="I've given you roles in all servers I can!")
        except Scout.exceptions.NoCode_NSVerify:
            await _message.edit(content="You need to give me the code")
        except Scout.exceptions.InvalidCode_NSVerify as Code:
            await _message.edit(
                content="Hmm...{} isn't right. Maybe cast scry and you'll find the right one...".format(Code.args[0]))
        except (Scout.exceptions.NoGuilds, Scout.exceptions.NoRoles):
            await _message.edit(content="I can't give you any roles right now. Thanks for the character-sheet though!")
        except Scout.exceptions.NoAssociations:
            await _message.edit(content="Oh...I don't think I have a roles I can give for that...")

    @commands.hybrid_command()  # type: ignore
    @commands.guild_only()
    async def unverify_nation(self, ctx, nation_name: str):
        """A command to remove a nation that you've verified.

        Parameters:
            ctx: The message context
            nation_name: The name of the nation to remove.
        """
        with Session(self.scout.engine) as session:
            user = db.get_user(ctx.author.id, session=session)
            nation = db.get_nation(nation_name, session=session)

            if nation is None or user is None or nation not in user.nations:
                return

            try:
                user.nations.remove(nation)
            except (ValueError, KeyError):
                pass
            await self.give_verified_roles(ctx.author, session=session)

            session.commit()
        await ctx.send("I've removed your character sheet from my campaign notes.")

    @commands.hybrid_command()  # type: ignore
    @commands.check_any(commands.has_guild_permissions(administrator=True), commands.is_owner())
    @commands.guild_only()
    async def link_roles(self, ctx, verified_role: Optional[discord.Role], resident_role: Optional[discord.Role],
                         overwrite_roles: Optional[bool] = False):
        """The command to actually link two roles to the discord server.

        Parameters:
            ctx: The command context.
            verified_role: The role to use for users that are verified with the bot, but meet no other criteria.
            resident_role: The role to use for users that are in the server's associated region.

            overwrite_roles: If this is set, then the bot will replace any previously configured roles.
        """
        try:
            await ctx.send(self._link_roles(verified_role, resident_role, ctx.guild, overwrite=overwrite_roles))

            with Session(self.scout.engine) as session:
                users = session.scalars(select(User.snowflake)).all()
                if users:
                    members = await ctx.guild.query_members(user_ids=users)
                    for member in members:
                        await self.give_verified_roles(member, ctx.guild, session=session)

        except Scout.exceptions.NoRoles:
            await ctx.send("I don't know why you're trying to add roles without giving me any...")
        except Scout.exceptions.InvalidGuild:
            await ctx.send("Looks like you don't have a region associated with this server!")
        except Scout.exceptions.InvalidRole:
            await ctx.send("Oh no, I rolled a Nat 1! I can't currently add that role!")
        except Scout.exceptions.InvalidAssociation:
            await ctx.send("Oh no, I've lost my notes! I can't currently add roles!")
        except Scout.exceptions.RoleOverwrite:
            await ctx.send(
                "Unfortunately that would overwrite a role. Use `\\link_roles` with overwrite_roles set to True")

    @commands.hybrid_command()  # type: ignore
    @commands.check_any(commands.has_guild_permissions(administrator=True), commands.is_owner())
    @commands.guild_only()
    async def unlink_roles(self, ctx, verified_role: Optional[discord.Role], resident_role: Optional[discord.Role],
                           remove_roles: Optional[bool] = True):
        """A command to remove the roles from being managed by the bot.

        Parameters:
            ctx: The command context.
            verified_role: The verified role to remove, if you want to remove it.
            resident_role: The resident role to remove, if you want to remove it.

            remove_roles: If set to True, it will also remove the roles from any users with the role set.
        """
        unlinked_roles: list[discord.Role] = []

        # Note: Check the remove_role function
        with Session(self.scout.engine) as session:
            guild_id = session.scalar(select(models.Guild).where(models.Guild.snowflake == ctx.guild.id)).id
            if verified_role:
                unlinked_roles.append(verified_role)
                role = session.scalar(select(models.Role)
                                      .join(models.role_associations)
                                      .join(models.Association)
                                      .where(models.Association.id == self.scout.associations[VERIFIED])
                                      .where(models.Role.guild_id == guild_id))
                if role is not None:
                    session.delete(role)
            if resident_role:
                unlinked_roles.append(resident_role)
                role = session.scalar(select(models.Role)
                                      .join(models.role_associations)
                                      .join(models.Association)
                                      .where(models.Association.id == self.scout.associations[RESIDENT])
                                      .where(models.Role.guild_id == guild_id))
                if role is not None:
                    session.delete(role)
            session.commit()

        if remove_roles:
            for role in unlinked_roles:
                for member in role.members:
                    await member.remove_roles(role)
        if unlinked_roles:
            await ctx.send("I've gone ahead and removed that role from my notes!")
        else:
            await ctx.send("You didn't give me any valid roles to remove from notes!...")

    async def register_nation(self, nation_name: str, message: discord.Message, *, session: Session) -> str:
        """Actually register the 'nation' to the bot.

        Parameters:
            nation_name: The NS Nation to use.
            message: The message to use for responses.
            session: The database session.

        Returns:
            A string to send to user.
        """
        nation = db.get_nation(nation_name.casefold(), session=session)

        if nation is None:
            nation = await self.ns_client.get_nation(nation_name, shards=None, user_agent=self.user_agent)
            region = db.get_region(nation["REGION"].casefold(), session=session)

            if region is None:
                region = await self.ns_client.get_region(nation["REGION"], shards=None, user_agent=self.user_agent)
                region = Region(name=region["NAME"].casefold(), data=region)
                session.add(region)

            nation = Nation(name=nation["NAME"].casefold(),
                            data=nation,
                            region=region)
            session.add(nation)

        user = db.register_user(message.author.id, session=session)
        db.link_user_nation(user, nation, session=session)
        session.commit()
        return "There we go! I'll see if I can get you some roles..."

    @staticmethod
    async def eligible_nsv_role(user: discord.Member, guild: models.Guild, session: Session) -> str | None:
        """Determine what roles the user is eligible for in the given server.

        Parameters:
            user: The discord user
            guild: The discord guild
            session: The database session to use.
        """
        eligible_role = None
        user_db = db.get_user(user.id, session=session)

        if guild is None or user_db is None:
            return None

        if user is not None:
            eligible_role = VERIFIED

        if guild.regions & {n.region for n in user_db.nations}:
            eligible_role = RESIDENT

        return eligible_role

    @staticmethod
    async def ineligible_nsv_roles(eligible_role: str | None) -> list[str]:
        """Determine if there are any roles we are not elligble for.

        Parameters:
            elligble_role: The role they are elligble for in the server.
        """
        if eligible_role == RESIDENT:
            return [VERIFIED]
        elif eligible_role == VERIFIED:
            return [RESIDENT]
        else:
            return [RESIDENT, VERIFIED]

    async def give_verified_roles(self, user: discord.User | discord.Member, guild: Optional[discord.Guild] = None,
                                  *, session: Session):
        if not session.scalars(select(models.Role)).all():
            return

        user_db = db.get_user(user.id, session=session)
        if user_db is None or not user_db.nations:
            return

        mutual_guilds = {}
        active_guilds = []
        if guild is None:
            mutual_guilds = {g.id: (g, m) for g in self.scout.guilds if (m := await g.fetch_member(user.id))}
            active_guilds = session.scalars(
                select(models.Guild).where(models.Guild.snowflake.in_(mutual_guilds.keys()))).all()
            if not active_guilds:
                return

        else:
            mutual_guilds[guild.id] = (guild, user)
            active_guilds = [session.scalar(select(models.Guild).where(models.Guild.snowflake == guild.id))]
            active_guilds = [g for g in active_guilds if g is not None]
            if not active_guilds:
                return

        for active_guild in active_guilds:
            if mutual_guilds[active_guild.snowflake][1] is None or not active_guild.roles:
                continue

            user = mutual_guilds[active_guild.snowflake][1]

            eligible_roles = await self.eligible_nsv_role(user, active_guild, session=session)
            ineligible_roles = await self.ineligible_nsv_roles(eligible_roles)
            eligible_guild_role = session.scalar(select(models.Role)
                                        .join(models.role_associations)
                                        .join(models.Association)
                                        .where(models.Role.guild_id == active_guild.id)
                                        .where(models.Association.id == self.scout.associations[eligible_roles]))

            ineligible_guild_role = lambda a: (select(models.Role)
                                               .join(models.role_associations)
                                               .join(models.Association)
                                               .where(models.Role.guild_id == active_guild.id)
                                               .where(models.Association.id == self.scout.associations[a]))
            ineligible_db = [session.scalar(ineligible_guild_role(r))
                             for r in ineligible_roles if r is not None]
            discord_roles = [discord.Object(r.snowflake) for r in ineligible_db if r is not None]

            if eligible_guild_role is not None:
                eligible_discord = discord.Object(eligible_guild_role.snowflake)
                await user.add_roles(eligible_discord)
            await user.remove_roles(*discord_roles)

    async def _verify_nation(self, nation: str, code: Optional[str]) -> tuple[str]:
        if code is None:
            raise Scout.exceptions.NoCode_NSVerify()

        response = await self.ns_client.get_verify(nation, code, user_agent=self.user_agent)
        if not response:
            raise Scout.exceptions.InvalidCode_NSVerify(code)

        return "You're verified! Let me put this character-sheet in my campaign binder.", nation

    @commands.hybrid_command()  # type: ignore
    async def verified_nations(self, ctx, private_response: Optional[bool] = True):
        """
        Displays Verified Nations of a given user.
        """
        with Session(self.scout.engine) as session:
            user = db.get_user(ctx.message.author.id, snowflake_only=True, session=session)
        if user is not None and user.nations:
            await ctx.send('\n'.join([n.name for n in user.nations]), ephemeral=private_response)
        await ctx.send("I don't have any nations for you!")

    @commands.Cog.listener('on_member_join')
    async def verify_on_join(self, member: discord.Member):
        with Session(self.scout.engine) as session:
            await self.give_verified_roles(member, member.guild, session=session)


async def setup(bot):
    """
    setup function to make this module into an extension.
    """
    await bot.add_cog(NSVerify(bot, bot.ns_client))
