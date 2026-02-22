from sqlalchemy import Integer, Float, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class PitStop(Base):
    __tablename__ = "pitstops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    stop_number: Mapped[int] = mapped_column(Integer)
    lap: Mapped[int] = mapped_column(Integer)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=True)
    tyre_compound: Mapped[str] = mapped_column(String(50), nullable=True)

    race: Mapped["Race"] = relationship("Race", back_populates="pitstops")