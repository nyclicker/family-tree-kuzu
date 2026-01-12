import uuid, enum
from sqlalchemy import String, Text, ForeignKey, Date, Enum, Integer, DateTime, func, Boolean, JSON
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


class Tree(Base):
    __tablename__ = "trees"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False, server_default=func.now())
    versions: Mapped[list["TreeVersion"]] = relationship("TreeVersion", back_populates="tree")


class TreeVersion(Base):
    __tablename__ = "tree_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tree_id: Mapped[int] = mapped_column(Integer, ForeignKey("trees.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_filename: Mapped[str | None] = mapped_column(String(400), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False, server_default=func.now())
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tree: Mapped["Tree"] = relationship("Tree", back_populates="versions")


class WorkingChange(Base):
    __tablename__ = "working_changes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tree_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("trees.id"), nullable=True)
    base_tree_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tree_versions.id"), nullable=True)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False, server_default=func.now())

class Person(Base):
    __tablename__ = "person"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    sex: Mapped[Sex] = mapped_column(Enum(Sex), nullable=False, default=Sex.U)
    birth_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    death_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tree_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("trees.id"), nullable=True)
    tree_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tree_versions.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

class Relationship(Base):
    __tablename__ = "relationship"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    from_person_id: Mapped[str] = mapped_column(String(36), ForeignKey("person.id"), nullable=False)

    # ✅ allow NULL for EARLIEST_ANCESTOR
    to_person_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("person.id"), nullable=True)

    type: Mapped[RelType] = mapped_column(Enum(RelType), nullable=False)
    tree_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("trees.id"), nullable=True)
    tree_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tree_versions.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    from_person = relationship("Person", foreign_keys=[from_person_id])
    to_person = relationship("Person", foreign_keys=[to_person_id])
