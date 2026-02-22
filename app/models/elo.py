from sqlalchemy import Integer, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class ConstructorElo(Base):
    __tablename__ = "constructor_elo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    constructor_id: Mapped[int] = mapped_column(ForeignKey("constructors.id"), index=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), index=True)
    elo_before: Mapped[float] = mapped_column(Float)
    elo_after: Mapped[float] = mapped_column(Float)
    date: Mapped[str] = mapped_column(String(20))

    constructor: Mapped["Constructor"] = relationship("Constructor", back_populates="elo_ratings")