from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Constructor(Base):
    __tablename__ = "constructors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ergast_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    nationality: Mapped[str] = mapped_column(String(100))

    elo_ratings: Mapped[list["ConstructorElo"]] = relationship("ConstructorElo", back_populates="constructor")