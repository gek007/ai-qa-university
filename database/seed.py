"""Populate the database with deterministic sample data via the ORM.

Run directly:  python -m database.seed
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from database.db import Database
from database.models import Course, CourseOffering, Enrollment, Student, Teacher

TEACHERS = [
    "Dr. Alice Cohen",
    "Prof. Ben Levi",
    "Dr. Clara Stein",
    "Prof. David Roth",
    "Dr. Emma Shapiro",
]

STUDENTS = [
    "Noa Bar", "Ethan Katz", "Maya Gold", "Liam Ben-David", "Sara Mor",
    "Yuval Peled", "Tamar Azulay", "Omer Dayan", "Hila Friedman", "Ariel Weiss",
    "Roni Shani", "Ido Harel", "Lior Tal", "Shira Naor", "Gal Avraham",
    "Dana Ron", "Eitan Segal", "Noam Ziv", "Talia Rubin", "Yoav Edri",
]

COURSES = [
    "Introduction to AI",
    "Database Systems",
    "Operating Systems",
    "Linear Algebra",
    "Data Structures",
    "Machine Learning",
    "Computer Networks",
    "Software Engineering",
]

SEMESTERS = ["Fall 2024", "Spring 2025", "Fall 2025"]

OFFERINGS = [
    ("Introduction to AI",     "Dr. Alice Cohen",   "Fall 2024"),
    ("Introduction to AI",     "Dr. Alice Cohen",   "Fall 2025"),
    ("Database Systems",       "Prof. Ben Levi",    "Fall 2024"),
    ("Database Systems",       "Prof. Ben Levi",    "Spring 2025"),
    ("Operating Systems",      "Prof. Ben Levi",    "Fall 2025"),
    ("Linear Algebra",         "Dr. Clara Stein",   "Fall 2024"),
    ("Linear Algebra",         "Dr. Clara Stein",   "Spring 2025"),
    ("Data Structures",        "Prof. David Roth",  "Fall 2024"),
    ("Data Structures",        "Prof. David Roth",  "Fall 2025"),
    ("Machine Learning",       "Dr. Alice Cohen",   "Spring 2025"),
    ("Machine Learning",       "Dr. Emma Shapiro",  "Fall 2025"),
    ("Computer Networks",      "Prof. David Roth",  "Spring 2025"),
    ("Computer Networks",      "Prof. David Roth",  "Fall 2025"),
    ("Software Engineering",   "Dr. Emma Shapiro",  "Spring 2025"),
    ("Software Engineering",   "Dr. Emma Shapiro",  "Fall 2025"),
]


def _enrollments_plan() -> list[tuple[int, int, float | None]]:
    """Return a deterministic list of (student_idx, offering_idx, grade) tuples.

    Grade distribution is spread so aggregation queries produce meaningful,
    predictable results. Some enrollments have no grade (in-progress).
    """
    plan: list[tuple[int, int, float | None]] = []
    base_grades = [55, 62, 70, 74, 78, 82, 85, 88, 91, 95]

    for s_idx in range(len(STUDENTS)):
        for i, offering_idx in enumerate(
            [s_idx % 15, (s_idx + 3) % 15, (s_idx + 7) % 15]
        ):
            grade: float | None = float(base_grades[(s_idx + i * 2) % len(base_grades)])
            if (s_idx + offering_idx) % 11 == 0:
                grade = None
            plan.append((s_idx, offering_idx, grade))
    return plan


def seed(database: Database, *, reset: bool = True) -> None:
    """Populate (optionally resetting) the database with sample data."""
    if reset:
        database.drop_schema()
    database.create_schema()

    with database.session() as session:  # type: Session
        teachers = [Teacher(name=name) for name in TEACHERS]
        students = [Student(name=name) for name in STUDENTS]
        courses = [Course(title=title) for title in COURSES]
        session.add_all(teachers + students + courses)
        session.flush()

        teachers_by_name = {t.name: t for t in teachers}
        courses_by_title = {c.title: c for c in courses}

        offerings = [
            CourseOffering(
                course=courses_by_title[course_title],
                teacher=teachers_by_name[teacher_name],
                semester=semester,
            )
            for course_title, teacher_name, semester in OFFERINGS
        ]
        session.add_all(offerings)
        session.flush()

        enrollments = [
            Enrollment(
                student=students[s_idx],
                offering=offerings[off_idx],
                grade=grade,
            )
            for s_idx, off_idx, grade in _enrollments_plan()
        ]
        session.add_all(enrollments)
        session.commit()


if __name__ == "__main__":
    db = Database()
    seed(db)
    print(f"Seeded {db.url}")
