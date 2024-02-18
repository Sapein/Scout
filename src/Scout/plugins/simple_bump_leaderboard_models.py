from sqlalchemy.orm import Mapped, mapped_column

from Scout.database.base import Base


class BumpLeaderBoard(Base):
    __tablename__ = "bump_leaderboard"

    guild_snowflake: Mapped[str] = mapped_column(primary_key=True)
    user_snowflake: Mapped[str] = mapped_column(primary_key=True)
    bump_count: Mapped[int] = mapped_column(default=0)
