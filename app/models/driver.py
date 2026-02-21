from sqlalchemy import String, Integer, Date
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    forename: Mapped[str] = mapped_column(String(100))
    surname: Mapped[str] = mapped_column(String(100))
    nationality: Mapped[str] = mapped_column(String(100))
    code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    career_points: Mapped[float] = mapped_column(default=0.0)