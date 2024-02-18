from datetime import datetime

import sqlalchemy.sql.functions
from sqlalchemy.orm import Mapped, mapped_column

from Scout.database.base import Base


class BumpLeaderBoard(Base):
    __tablename__ = "bump_leaderboard"

    guild_snowflake: Mapped[str] = mapped_column(primary_key=True)
    user_snowflake: Mapped[str] = mapped_column(primary_key=True)
    bump_count: Mapped[int] = mapped_column(default=0)


class BumpLog(Base):
    __tablename__ = "bump_log"

    guild_snowflake: Mapped[str] = mapped_column(primary_key=True)
    user_snowflake: Mapped[str] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(primary_key=True, server_default=sqlalchemy.sql.functions.now())
