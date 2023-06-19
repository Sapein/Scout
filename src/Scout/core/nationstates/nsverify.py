"""
This module contains all the stuff for NSVerify Functionality.
"""
import asyncio
from typing import Optional, Any

import discord
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm import Session

import Scout.exceptions
from Scout.database import db, models
from Scout.ns_api import ns
from Scout.core.nationstates import __VERSION__
from Scout.ns_api.nation import Nation

VERIFIED = "verified"
RESIDENT = "resident"


class NSVerify(commands.Cog):
    """
    NSVerify Cog
    """
    ns_client: ns.NationStatesClient
    users_verifying: dict[Any, Any] = {}

    def __init__(self, bot):
        self.scout = bot
        self.scout.register_meaning("verified", suppress_error=True)
        self.scout.register_meaning("resident", suppress_error=True)

    async def cog_load(self):
        user_agent = ns.create_user_agent(self.scout.config["CONTACT_INFO"],
                                          self.scout.config["NATION"],
                                          self.scout.config["REGION"])
        user_agent = "NSVerify-Cog/{} {}".format(__VERSION__, user_agent)
        self.ns_client = await ns.NationStatesClient(self.scout.reusable_session,
                                                     user_agent=user_agent).build()

    def link_roles(self, verified_role: Optional[discord.Role], resident_role: Optional[discord.Role],
                   guild: discord.Guild, overwrite: Optional[bool] = False) -> str:
        if verified_role is None and resident_role is None:
            raise Scout.exceptions.NoRoles()

        with Session(self.scout.engine) as session:
            guild = db.get_guild(guild.id, session=session)
            if resident_role is not None:
                self.scout.add_role(resident_role, guild, RESIDENT.casefold(), override=overwrite, session=session)

        if verified_role is not None and resident_role is not None:
            return ("A Natural 20, a critical success! I've obtained the mythical +1 roles of {} and {}!"
                    ).format(verified_role.name, resident_role.name)
        if verified_role is not None:
            return ("Looks like I found the mythical role of {}...now to find the other piece."
                    ).format(verified_role)
        return ("Looks like I found the mythical role of {}...now to find the other piece."
                ).format(resident_role)

    @commands.hybrid_command()  # type: ignore
    @commands.is_owner()
    @commands.guild_only()
    async def link_region(self, ctx, region_name: str, verified_role: Optional[discord.Role],
                          resident_role: Optional[discord.Role]):
        region = await self.ns_client.get_region(region_name)
        with Session(self.scout.engine) as session:
            new_region = db.register_region(region.name, session=session)
            new_guild = db.register_guild(guild_snowflake=ctx.guild.id, session=session)
            db.link_guild_region(new_guild, new_region, session=session)
            session.commit()  # flush?

            try:
                self.link_roles(verified_role, resident_role, ctx.message, overwrite=False)
                await ctx.send("The region has been registered to this server along with the roles!")

                users = session.scalars(select(models.User.snowflake)).all()
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
            except Scout.exceptions.InvalidMeaning:
                await ctx.send("Oh no, I've lost my notes! I can't currently add roles!")
            except Scout.exceptions.RoleOverwrite:
                await ctx.send(
                    "Unfortunately that would overwrite a role. Use `\\link_roles` with overwrite_roles set to True")

    @commands.hybrid_command()  # type: ignore
    @commands.is_owner()
    @commands.guild_only()
    async def unlink_region(self, ctx, region_name: str):
        with Session(self.scout.engine) as session:
            ns_region = await self.ns_client.get_region(region_name.replace(" ", "_"))
            region = db.get_region(ns_region.name, session=session)
            guild = db.get_guild(ctx.guild.id, session=session)

            if region is not None and guild is not None:
                if region in guild.regions:
                    db.unlink_guild_region(guild, region, session=session)
                    return await ctx.send("I've removed this region from my maps!")
                return await ctx.send("I couldn't find that region...")
            await ctx.send("I couldn't find that region or guild...")

    async def verify_dm_flow(self, ctx, nation: str):
        await ctx.send("Alrighty! Please check your DMs", ephemeral=True)
        message = await ctx.message.author.send(
            ("Hi please log into your {} now. After doing so go to this link: {}\n"
             "Copy the code from that page and paste it here.\n"
             "**__This code does not give anyone access to your nation or any control over it. It only allows me "
             "to verify identity__**\n"
             "Pretty cool, huh?").format(nation, self.ns_client.get_verify_url()))
        self.users_verifying[ctx.message.author.name] = (nation, message)

        await asyncio.sleep(60)
        if ctx.message.author in self.users_verifying:
            await ctx.message.author.send((
                "Oh, you didn't want to verify? That's fine. If you change your mind just `/verify_nation` again!"))
            del self.users_verifying[ctx.message.author.name]

    @commands.hybrid_command()  # type: ignore
    @commands.guild_only()
    async def verify_nation(self, ctx, code: Optional[str], nation: str):
        """
        Verifies a nation and assigns it to a user.
        """
        nation = await self.ns_client.get_nation(nation.replace(" ", "_"))
        with Session(self.scout.engine) as session:
            if db.get_nation(nation.name, session=session):
                await ctx.send("That nation has a character sheet already, silly!", ephemeral=True)
                return

        if code is None:
            await self.verify_dm_flow(ctx, nation.name)
        else:
            try:
                message = None
                async with ctx.typing(ephemeral=True):
                    res, ns_nation = await self._verify_nation(nation.name, code)
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
            except (Scout.exceptions.NoGuilds, Scout.exceptions.NoRoles, Scout.exceptions.NoMeanings,
                    Scout.exceptions.NoNation, Scout.exceptions.NoCode_NSVerify):
                await ctx.send("There was an internal error...", ephemeral=True)
                raise

    @commands.Cog.listener('on_message')
    async def verify_nation_msg(self, message):
        if message.guild is not None or message.author.name in self.users_verifying:
            return
        (nation, _message) = self.users_verifying[message.author.name]
        try:
            async with message.channel.typing():
                res, nation = await self._verify_nation(nation, message.content)
            await _message.edit(content=res)

            async with message.channel.typing():
                res = await self.scout.register_nation(nation, message)
            await _message.edit(content=res)

            async with message.channel.typing():
                del self.users_verifying[message.author.name]
                await self.scout.give_verified_roles(message.author)
            await _message.edit(content="I've given you roles in all servers I can!")
        except Scout.exceptions.NoCode_NSVerify:
            await _message.edit(content="You need to give me the code")
        except Scout.exceptions.InvalidCode_NSVerify as Code:
            await _message.edit(
                content="Hmm...{} isn't right. Maybe cast scry and you'll find the right one...".format(Code.args[0]))
        except (Scout.exceptions.NoGuilds, Scout.exceptions.NoRoles):
            await _message.edit(content="I can't give you any roles right now. Thanks for the character-sheet though!")
        except Scout.exceptions.NoMeanings:
            await _message.edit(content="Oh...I don't think I have a roles I can give for that...")

    @commands.hybrid_command()  # type: ignore
    @commands.guild_only()
    async def unverify_nation(self, ctx, nation_name: str):
        with Session(self.scout.engine) as session:
            user = db.get_user(ctx.author.id, session=session)

            ns_nation = await self.scout.ns_client.get_nation(nation_name)
            nation = db.get_nation(ns_nation.name, session=session)

            if nation is None or user is None or nation not in user.nations:
                return

            try:
                user.nations.remove(nation)
            except (ValueError, KeyError):
                pass
            await self.give_verified_roles(ctx.author, session=session)

            if not nation.users:
                session.delete(nation)

            if not user.nations:
                session.delete(user)

            session.commit()
        await ctx.send("I've removed your character sheet from my campaign notes.")

    @commands.hybrid_command()  # type: ignore
    @commands.is_owner()
    @commands.guild_only()
    async def link_roles(self, ctx, verified_role: Optional[discord.Role], resident_role: Optional[discord.Role],
                         overwrite_roles: Optional[bool] = False):
        try:
            await ctx.send(self.link_roles(verified_role, resident_role, ctx.message, overwrite=overwrite_roles))

            with Session(self.scout.engine) as session:
                users = session.scalars(select(models.User.snowflake)).all()
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
        except Scout.exceptions.InvalidMeaning:
            await ctx.send("Oh no, I've lost my notes! I can't currently add roles!")
        except Scout.exceptions.RoleOverwrite:
            await ctx.send(
                "Unfortunately that would overwrite a role. Use `\\link_roles` with overwrite_roles set to True")

    @commands.hybrid_command()  # type: ignore
    @commands.is_owner()
    @commands.guild_only()
    async def unlink_roles(self, ctx, verified_role: Optional[discord.Role], resident_role: Optional[discord.Role],
                           remove_roles: Optional[bool] = True):
        unlinked_roles: list[discord.Role] = []
        if verified_role and (res := self.scout.remove_role(verified_role)) is not None:
            unlinked_roles.append(res)
        if resident_role and (res := self.scout.remove_role(resident_role)) is not None:
            unlinked_roles.append(res)

        if remove_roles:
            for role in unlinked_roles:
                for member in role.members:
                    await member.remove_roles(role)
        if unlinked_roles:
            await ctx.send("I've gone ahead and removed that role from my notes!")
        else:
            await ctx.send("You didn't give me any valid roles to remove from notes!...")

    @staticmethod
    async def register_nation(nation: Nation, message: discord.Message, *, session: Session) -> str:
        region = db.get_region(nation.region, session=session)
        if region is None:
            region = db.register_region(nation.region, session=session)

        user = db.register_user(message.author.id, session=session)
        nation = db.register_nation(nation.name, region_info=region, session=session)
        db.link_user_nation(user, nation, session=session)
        return "There we go! I'll see if I can get you some roles..."

    async def eligible_nsv_role(self, user: discord.Member, guild: models.Guild, session: Session) -> str | None:
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
        if eligible_role == RESIDENT:
            return [VERIFIED]
        elif eligible_role == VERIFIED:
            return [RESIDENT]
        else:
            return [RESIDENT, VERIFIED]

    async def give_verified_roles(self, user: discord.User | discord.Member, guild: Optional[discord.Guild] = None,
                                  *, session: Session):
        if not session.scalars(select(models.Role)).all():
            raise Scout.exceptions.NoRoles()

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
                raise Scout.exceptions.NoGuilds()

        else:
            mutual_guilds[guild.id] = user
            active_guilds = [db.get_guild(guild.id, session=session)]
            active_guilds = [g for g in active_guilds if g is not None]
            if not active_guilds:
                return

        for active_guild in active_guilds:
            if mutual_guilds[active_guild.snowflake][1] is None or not active_guild.roles:
                continue

            user = mutual_guilds[active_guild.snowflake][1]

            eligible_roles = await self.eligible_nsv_role(user, active_guild, session=session)
            ineligible_roles = await self.ineligible_nsv_roles(eligible_roles)
            eligible_discord = discord.Object(db.get_guildrole_with_meaning(active_guild,
                                                                            eligible_roles,
                                                                            session=session).snowflake)

            ineligible_db = [db.get_guildrole_with_meaning(active_guild, r, session=session)
                             for r in ineligible_roles]
            discord_roles = [discord.Object(r.snowflake) for r in ineligible_db if r is not None]

            await user.add_roles(eligible_discord)
            await user.remove_roles(*discord_roles)

    async def _verify_nation(self, nation: Nation | str, code: Optional[str]) -> tuple[str, Nation]:
        if code is None:
            raise Scout.exceptions.NoCode_NSVerify()

        response, nation = await self.ns_client.verify(nation, code)
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
    await bot.add_cog(NSVerify(bot))
