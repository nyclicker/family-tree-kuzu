import uuid, enum
from sqlalchemy import String, Text, ForeignKey, Date, Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Sex(enum.Enum):
    M = "M"
    F = "F"
    U = "U"

class RelType(enum.Enum):
    CHILD_OF = "CHILD_OF"
    EARLIEST_ANCESTOR = "EARLIEST_ANCESTOR"

class Person(Base):
    __tablename__ = "person"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    sex: Mapped[Sex] = mapped_column(Enum(Sex), nullable=False, default=Sex.U)
    birth_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    death_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

class Relationship(Base):
    __tablename__ = "relationship"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    from_person_id: Mapped[str] = mapped_column(String(36), ForeignKey("person.id"), nullable=False)

    # ✅ allow NULL for EARLIEST_ANCESTOR
    to_person_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("person.id"), nullable=True)

    type: Mapped[RelType] = mapped_column(Enum(RelType), nullable=False)

    from_person = relationship("Person", foreign_keys=[from_person_id])
    to_person = relationship("Person", foreign_keys=[to_person_id])
