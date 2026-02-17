from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = "shortnovels_secret_key"

# ---------------- DATABASE CONFIG ----------------

# USE SUPABASE DATABASE_URL FROM RENDER ENVIRONMENT
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")

# Fix for Supabase (sometimes needs ssl)
if app.config["SQLALCHEMY_DATABASE_URI"] and app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgres://"):
    app.config["SQLALCHEMY_DATABASE_URI"] = app.config["SQLALCHEMY_DATABASE_URI"].replace("postgres://", "postgresql://")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ---------------- FILE UPLOAD CONFIG ----------------

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "covers")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ---------------- DATABASE MODELS ----------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)


class Novel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    short_description = db.Column(db.String(300))
    genre = db.Column(db.String(100))
    cover = db.Column(db.String(300))


class Chapter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("novel.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="published")
    views = db.Column(db.Integer, default=0)


class Library(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    novel_id = db.Column(db.Integer, db.ForeignKey("novel.id"))


# CREATE TABLES IN SUPABASE
with app.app_context():
    db.create_all()

# ---------------- ROUTES ----------------

@app.route("/")
def home():
    return redirect("/novels")


# -------- REGISTER --------
@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        if User.query.filter_by(username=username).first():
            error = "Username already exists"
        elif User.query.filter_by(email=email).first():
            error = "Email already exists"
        else:
            user = User(username=username, email=email, password=password)
            db.session.add(user)
            db.session.commit()
            return redirect("/login")

    return render_template("register.html", error=error)


# -------- LOGIN --------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == "danking" and password == "danking123":
            session["user_id"] = -1
            session["username"] = "danking"
            session["email"] = "admin@shortnovels.com"
            session["is_admin"] = True
            return redirect("/admin")

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["email"] = user.email
            session["is_admin"] = False
            return redirect("/novels")
        else:
            error = "Invalid login details"

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# -------- NOVELS --------
@app.route("/novels")
def novels():
    page = request.args.get("page", 1, type=int)
    per_page = 10

    pagination = Novel.query.paginate(page=page, per_page=per_page)
    novels_page = pagination.items

    novels_data = []
    for novel in novels_page:
        first_chapter = (
            Chapter.query
            .filter_by(novel_id=novel.id, status="published")
            .order_by(Chapter.id.asc())
            .first()
        )
        novels_data.append({"novel": novel, "first_chapter": first_chapter})

    return render_template("novels.html", novels_data=novels_data, pagination=pagination)


# -------- CHAPTERS --------
@app.route("/novel/<int:novel_id>/chapters")
def novel_chapters(novel_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    novel = Novel.query.get_or_404(novel_id)

    chapters = (
        Chapter.query
        .filter_by(novel_id=novel.id, status="published")
        .order_by(Chapter.id.asc())
        .all()
    )

    return render_template("chapters.html", novel=novel, chapters=chapters)


# -------- ADMIN --------
@app.route("/admin")
def admin():
    if not session.get("is_admin"):
        return redirect("/login")

    novels = Novel.query.all()
    users = User.query.all()
    return render_template("admin.html", novels=novels, users=users)


# -------- ADD NOVEL --------
@app.route("/add_novel", methods=["GET", "POST"])
def add_novel():
    if not session.get("is_admin"):
        return redirect("/login")

    error = None
    success = None

    if request.method == "POST":
        title = request.form.get("title")
        genre = request.form.get("genre")
        description = request.form.get("description")

        if not title or not genre or not description:
            error = "All fields except cover are required."
        else:
            cover_file = request.files.get("cover")
            cover_path = None

            if cover_file and cover_file.filename != "":
                filename = secure_filename(cover_file.filename)
                save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                cover_file.save(save_path)
                cover_path = f"covers/{filename}"

            novel = Novel(
                title=title,
                description=description,
                short_description=description[:200] + "...",
                genre=genre,
                cover=cover_path
            )

            try:
                db.session.add(novel)
                db.session.commit()
                success = "Novel added successfully!"
            except Exception as e:
                db.session.rollback()
                error = str(e)

    return render_template("add_novel.html", error=error, success=success)


if __name__ == "__main__":
    app.run(debug=True)
