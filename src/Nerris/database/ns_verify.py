"""
"""

from sqlalchemy import Table, Column, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, relationship
from Nerris.database.base import Base
from Nerris.database import nationstates, discord


user_nations = Table(
    "user_nations",
    Base.metadata,
    Column("nation_id", ForeignKey="nations.id", primary_key=True),
    Column("users_id", ForeignKey="users.id", primary_key=True),
)

guild_regions = Table(
    "guild_regions",
    Base.metadata,
    Column("nation_id", ForeignKey="regions.id", primary_key=True),
    Column("guild_id", ForeignKey="guild.id", primary_key=True),
)
