from flask import Flask, render_template, request, redirect, url_for, flash, Response
from models import db, User, Exercise, WorkoutPlan, WorkoutPlanExercise, WorkoutEntry
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from collections import defaultdict
from datetime import datetime, timedelta
import json

app = Flask(__name__)
app.config["SECRET_KEY"] = "to-aaron-love-jackson"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///workout.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "home"  # redirect here if not logged in

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash("Invalid username or password.", "ERROR")
            return redirect(url_for("home"))

        login_user(user)
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # validation
        if username == "" or password == "":
            flash("Username and password are required.", "ERROR")
            return redirect(url_for("register"))

        # check for duplicate username
        existing_user = User.query.filter_by(username=username).first()
        if existing_user is not None:
            flash("That username is already taken.", "ERROR")
            return redirect(url_for("register"))

        # create new user
        new_user = User(username=username, email=email if email != "" else None)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully. Please log in.", "SUCCESS")
        return redirect(url_for("home"))

    # GET request to shows the form
    return render_template("register.html")

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "SUCCESS")
    return redirect(url_for("home"))

@app.route("/exercises")
@login_required
def exercises():
    all_exercises = Exercise.query.order_by(Exercise.muscle_group, Exercise.name).all()
    return render_template("exercises.html", exercises=all_exercises)

@app.route("/exercises/new", methods=["GET", "POST"])
@login_required
def new_exercise():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        muscle_group = request.form.get("muscle_group", "").strip()
        exercise_type = request.form.get("exercise_type", "").strip()

        if name == "" or muscle_group == "" or exercise_type == "":
            flash("Exercise name, muscle group, and type are required.", "ERROR")
            return redirect(url_for("new_exercise"))

        ex = Exercise(
            name=name,
            muscle_group=muscle_group,
            exercise_type=exercise_type
        )
        db.session.add(ex)
        db.session.commit()

        flash("Exercise added successfully.", "SUCCESS")
        return redirect(url_for("exercises"))

    return render_template("exercise_form.html", mode="Create", exercise=None)

@app.route("/exercises/<int:exercise_id>/edit", methods=["GET", "POST"])
@login_required
def edit_exercise(exercise_id: int):
    ex = Exercise.query.get_or_404(exercise_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        muscle_group = request.form.get("muscle_group", "").strip()
        exercise_type = request.form.get("exercise_type", "").strip()

        if name == "" or muscle_group == "" or exercise_type == "":
            flash("Exercise name, muscle group, and type are required.", "ERROR")
            return redirect(url_for("edit_exercise", exercise_id=exercise_id))

        ex.name = name
        ex.muscle_group = muscle_group
        ex.exercise_type = exercise_type
        db.session.commit()

        flash("Exercise updated successfully.", "SUCCESS")
        return redirect(url_for("exercises"))

    return render_template("exercise_form.html", mode="Update", exercise=ex)

@app.route("/exercises/<int:exercise_id>/delete")
@login_required
def delete_exercise(exercise_id: int):
    ex = Exercise.query.get_or_404(exercise_id)
    db.session.delete(ex)
    db.session.commit()
    flash("Exercise deleted.", "SUCCESS")
    return redirect(url_for("exercises"))

@app.route("/plans/new", methods=["GET", "POST"])
@login_required
def create_plan():
    exercises = Exercise.query.order_by(Exercise.name).all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()

        # list of  exercises comes from the hidden json field
        items_json = request.form.get("items_json", "[]")
        try:
            items = json.loads(items_json)
        except json.JSONDecodeError:
            items = []

        # validation
        if name == "":
            flash("Plan name is required.", "ERROR")
            return redirect(url_for("create_plan"))

        if not items:
            flash("Please add at least one exercise to the plan.", "ERROR")
            return redirect(url_for("create_plan"))

        # create the plan
        plan = WorkoutPlan(name=name, user_id=current_user.user_id)
        db.session.add(plan)
        db.session.commit()  # commit first so plan.plan_id exists

        # Add exercises
        for item in items:
            # defensive parsing
            try:
                exercise_id = int(item.get("exercise_id"))
                sets_int = int(item.get("sets"))
                reps_int = int(item.get("reps"))
            except (TypeError, ValueError):
                db.session.rollback()
                flash("Invalid sets/reps data. Please re-enter values.", "ERROR")
                return redirect(url_for("create_plan"))

            # extra validation
            if sets_int <= 0 or reps_int <= 0:
                db.session.rollback()
                flash("Sets and reps must be greater than 0.", "ERROR")
                return redirect(url_for("create_plan"))

            wpe = WorkoutPlanExercise(
                plan_id=plan.plan_id,
                exercise_id=exercise_id,
                sets=sets_int,
                reps=reps_int
            )
            db.session.add(wpe)

        db.session.commit()
        flash("Workout plan created successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("create_plan.html", exercises=exercises)

@app.route("/log", methods=["GET", "POST"])
@login_required
def log_workout():
    exercises = Exercise.query.order_by(Exercise.name).all()


    if request.method == "POST":
        exercise_id = request.form.get("exercise_id", "")
        date = request.form.get("date", "").strip()
        sets = request.form.get("sets", "").strip()
        reps = request.form.get("reps", "").strip()
        weight = request.form.get("weight", "").strip()


        if exercise_id == "" or date == "" or sets == "" or reps == "":
            flash("Exercise, date, sets, and reps are required.", "ERROR")
            return redirect(url_for("log_workout"))


        try:
            sets_int = int(sets)
            reps_int = int(reps)
            weight_int = int(weight) if weight != "" else None
        except ValueError:
            flash("Sets, reps, and weight must be numbers.", "ERROR")
            return redirect(url_for("log_workout"))


        entry = WorkoutEntry(
            user_id=current_user.user_id,
            exercise_id=int(exercise_id),
            date=date,
            sets=sets_int,
            reps=reps_int,
            weight=weight_int
        )


        db.session.add(entry)
        db.session.commit()


        flash("Workout entry saved.", "SUCCESS")
        return redirect(url_for("dashboard"))


    return render_template("log_workout.html", exercises=exercises)



@app.route("/progress", methods=["GET"])
@login_required
def progress():
    exercises = Exercise.query.order_by(Exercise.name).all()

    selected_id = request.args.get("exercise_id", type=int)

    labels, values = [], []
    if selected_id:
        entries = (WorkoutEntry.query
            .filter_by(user_id=current_user.user_id, exercise_id=selected_id)
            .order_by(WorkoutEntry.date.asc())
            .all())

        for e in entries:
            labels.append(e.date.strftime("%Y-%m-%d") if hasattr(e.date, "strftime") else str(e.date))
            values.append(e.weight if e.weight is not None else e.reps)

    return render_template(
        "progress.html",
        exercises=exercises,
        selected_id=selected_id,
        labels=labels,
        values=values
    )


@app.route("/reminders", methods=["GET", "POST"])
@login_required
def reminders():
    plans = WorkoutPlan.query.filter_by(user_id=current_user.user_id).order_by(WorkoutPlan.name).all()

    if request.method == "POST":
        plan_id = request.form.get("plan_id", type=int)
        date_str = request.form.get("date", "").strip()   # YYYY-MM-DD from <input type="date">
        time_str = request.form.get("time", "").strip()   # HH:MM from <input type="time">

        if not plan_id or date_str == "" or time_str == "":
            flash("Plan, date, and time are required.", "ERROR")
            return redirect(url_for("reminders"))

        plan = WorkoutPlan.query.filter_by(plan_id=plan_id, user_id=current_user.user_id).first()
        if plan is None:
            flash("Invalid plan selected.", "ERROR")
            return redirect(url_for("reminders"))

        # datetime in local time
        dt_start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        dt_end = dt_start + timedelta(minutes=60)

        # timestamps
        dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        dtstart = dt_start.strftime("%Y%m%dT%H%M%S")
        dtend = dt_end.strftime("%Y%m%dT%H%M%S")

        safe_title = plan.name.replace(",", " ").replace(";", " ")
        description = f"Workout Plan: {plan.name}"

        ics_content = (
            "BEGIN:VCALENDAR\r\n"
            "VERSION:2.0\r\n"
            "PRODID:-//WorkoutPlannerIA//EN\r\n"
            "CALSCALE:GREGORIAN\r\n"
            "BEGIN:VEVENT\r\n"
            f"DTSTAMP:{dtstamp}\r\n"
            f"DTSTART:{dtstart}\r\n"
            f"DTEND:{dtend}\r\n"
            f"SUMMARY:{safe_title}\r\n"
            f"DESCRIPTION:{description}\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )

        filename = f"{plan.name.replace(' ', '_')}_reminder.ics"

        return Response(
            ics_content,
            mimetype="text/calendar",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    return render_template("reminders.html", plans=plans)

if __name__ == "__main__":
    # Create database tables the first time the app runs
    with app.app_context():
        db.create_all()
    app.run(debug=True)