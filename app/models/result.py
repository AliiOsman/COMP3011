from sqlalchemy import Integer, Float, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Result(Base):
    __tablename__ = "results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    constructor_id: Mapped[int] = mapped_column(ForeignKey("constructors.id"), index=True)
    grid: Mapped[int] = mapped_column(Integer, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=True)
    points: Mapped[float] = mapped_column(Float, default=0.0)
    laps: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(100), nullable=True)
    fastest_lap_time: Mapped[str] = mapped_column(String(20), nullable=True)

    race: Mapped["Race"] = relationship("Race", back_populates="results")