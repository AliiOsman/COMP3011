from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class TyreStint(Base):
    __tablename__ = "tyre_stints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), index=True)
    session_key: Mapped[int] = mapped_column(Integer, index=True)
    driver_number: Mapped[int] = mapped_column(Integer, index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=True, index=True)
    stint_number: Mapped[int] = mapped_column(Integer)
    compound: Mapped[str] = mapped_column(String(20), nullable=True)
    lap_start: Mapped[int] = mapped_column(Integer, nullable=True)
    lap_end: Mapped[int] = mapped_column(Integer, nullable=True)
    tyre_age_at_start: Mapped[int] = mapped_column(Integer, nullable=True)