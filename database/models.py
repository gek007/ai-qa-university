"""SQLAlchemy ORM models for the university domain.

Entities:
    Teacher, Student, Course        -- core entities (each has a name)
    CourseOffering                  -- a Course taught by a Teacher in a semester
    Enrollment                      -- a Student taking a CourseOffering with a grade
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    offerings: Mapped[list["CourseOffering"]] = relationship(
        back_populates="teacher", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Teacher(id={self.id}, name={self.name!r})"


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    enrollments: Mapped[list["Enrollment"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Student(id={self.id}, name={self.name!r})"


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)

    offerings: Mapped[list["CourseOffering"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Course(id={self.id}, title={self.title!r})"


class CourseOffering(Base):
    """A specific instance of a Course, taught by a Teacher in a given semester."""

    __tablename__ = "course_offerings"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    semester: Mapped[str] = mapped_column(String(20), nullable=False)

    course: Mapped["Course"] = relationship(back_populates="offerings")
    teacher: Mapped["Teacher"] = relationship(back_populates="offerings")
    enrollments: Mapped[list["Enrollment"]] = relationship(
        back_populates="offering", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"CourseOffering(id={self.id}, course_id={self.course_id}, "
            f"teacher_id={self.teacher_id}, semester={self.semester!r})"
        )


class Enrollment(Base):
    """A Student's enrollment in a CourseOffering, including the grade received."""

    __tablename__ = "enrollments"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    offering_id: Mapped[int] = mapped_column(
        ForeignKey("course_offerings.id"), nullable=False
    )
    grade: Mapped[float | None] = mapped_column(Float, nullable=True)

    student: Mapped["Student"] = relationship(back_populates="enrollments")
    offering: Mapped["CourseOffering"] = relationship(back_populates="enrollments")

    def __repr__(self) -> str:
        return (
            f"Enrollment(id={self.id}, student_id={self.student_id}, "
            f"offering_id={self.offering_id}, grade={self.grade})"
        )
