"""
"""

import Nerris.database.ns_verify
import Nerris.database.discord

from sqlalchemy.orm import DeclarativeBase, Mapped, relationship
from Nerris.database.base import Base

class Nation(Base):
    __tablename__ = "nations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))


    user: Mapped[discord.User] = relationship(secondary=ns_verify.user_nations, back_populates="nations")
    region: Mapped["Region"] = relationship(back_populates="nations")


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]

    nations: Mapped[set["Nation"]] = relationship(back_populates="region")
    guild = Mapped[discord.Guild] = relationship(secondary=ns_verify.guild_regions, back_populates="regions")


class RegionalMessageBoard(Base):
    __tablename__ = "rmb"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("nations.id"))
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
    message: Mapped[str]
    date: Mapped[int]

    author: Mapped["Nation"] = relationship()
    region: Mapped["Region"] = relationship()
