"""
"""

import Nerris.database.ns_verify
import Nerris.database.nationstates

from sqlalchemy.orm import DeclarativeBase, Mapped, relationship
from Nerris.database.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    snowflake: Mapped[str]

    nations: Mapped[set[nationstates.Nation]] = relationship(secondary=ns_verify.user_nations, back_populates="user")

class Guild(Base):
    __tablename__ = "guilds"

    id: Mapped[int] = mapped_column(primary_key=True)
    snowflake: Mapped[str]

    regions: Mapped[set[nationstates.Region]] = relationship(secondary=ns_verify.guild_regions, back_populates="guild")
