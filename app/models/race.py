from sqlalchemy import String, Integer, Float, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Race(Base):
    __tablename__ = "races"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ergast_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    round: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    date: Mapped[str] = mapped_column(String(20), nullable=True)
    circuit_id: Mapped[int] = mapped_column(ForeignKey("circuits.id"), index=True)

    circuit: Mapped["Circuit"] = relationship("Circuit", back_populates="races")
    pitstops: Mapped[list["PitStop"]] = relationship("PitStop", back_populates="race")
    results: Mapped[list["Result"]] = relationship("Result", back_populates="race")