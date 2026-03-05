from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        return str(self.user_id)
    
class Exercise(db.Model):
    __tablename__ = "exercises"

    exercise_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    muscle_group = db.Column(db.String(80), nullable=False)
    exercise_type = db.Column(db.String(50), nullable=False)

    def get_details(self) -> str:
        return f"{self.name} - {self.exercise_type} ({self.muscle_group})"
    
class WorkoutPlan(db.Model):
    __tablename__ = "workout_plans"

    plan_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)

    exercises = db.relationship(
        "WorkoutPlanExercise",
        backref="workout_plan",
        cascade="all, delete-orphan"
    )


class WorkoutPlanExercise(db.Model):
    __tablename__ = "workout_plan_exercises"

    wpe_id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("workout_plans.plan_id"), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey("exercises.exercise_id"), nullable=False)
    sets = db.Column(db.Integer, nullable=False)
    reps = db.Column(db.Integer, nullable=False)

    exercise = db.relationship("Exercise")

class WorkoutEntry(db.Model):
    __tablename__ = "workout_entries"

    entry_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey("exercises.exercise_id"), nullable=False)

    date = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD   
    sets = db.Column(db.Integer, nullable=False)
    reps = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Integer, nullable=True)

    exercise = db.relationship("Exercise")

    def get_summary(self) -> str:
        w = f", {self.weight} lbs" if self.weight is not None else ""
        return f"{self.date}: {self.sets}x{self.reps}{w}"

