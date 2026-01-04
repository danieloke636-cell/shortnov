from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func  # <-- add this line
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = "shortnovels_secret_key"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "database.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Set upload folder
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "covers")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)
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
    short_description = db.Column(db.String(300))  # new field
    genre = db.Column(db.String(100))             # new field
    cover = db.Column(db.String(300))             # path relative to /static/


with app.app_context():
    db.create_all()
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

        # ADMIN HARDCODED LOGIN
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

# -------- LOGOUT --------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# -------- NOVELS --------
@app.route("/novels")
def novels():
    page = request.args.get('page', 1, type=int)
    per_page = 10  # number of novels per page

    # paginate novels
    pagination = Novel.query.paginate(page=page, per_page=per_page)
    novels_page = pagination.items

    # create novels_data for template
    novels_data = []
    for novel in novels_page:
        # get first chapter for linking
        first_chapter = Chapter.query.filter_by(novel_id=novel.id, status="published") \
                                     .order_by(Chapter.id.asc()) \
                                     .first()
        novels_data.append({'novel': novel, 'first_chapter': first_chapter})

    return render_template(
        "novels.html",
        novels_data=novels_data,
        pagination=pagination
    )


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

    return render_template(
        "chapters.html",
        novel=novel,
        chapters=chapters
    )


# -------- LIBRARY --------
@app.route("/library")
def library():
    if not session.get("user_id"):
        return redirect("/login")
    saved = Library.query.filter_by(user_id=session["user_id"]).all()
    novel_ids = [s.novel_id for s in saved]
    novels = Novel.query.filter(Novel.id.in_(novel_ids)).all() if novel_ids else []
    return render_template("library.html", novels=novels)

# -------- ADMIN --------
@app.route("/admin")
def admin():
    if not session.get("is_admin"):
        return redirect("/login")
    novels = Novel.query.all() or []
    users = User.query.all() or []
    return render_template("admin.html", novels=novels, users=users)

# -------- ADD NOVEL / CHAPTER --------

@app.route("/add_novel", methods=["GET", "POST"])
def add_novel():
    # Only admins can access
    if not session.get("is_admin"):
        return redirect("/login")
    
    error = None
    success = None

    if request.method == "POST":
        title = request.form.get("title")
        author = request.form.get("author")
        genre = request.form.get("genre")
        description = request.form.get("description")
        status = request.form.get("status", "draft")  # default to draft

        if not title or not author or not genre or not description:
            error = "All fields except cover are required."
        else:
            # Handle cover upload
            cover_file = request.files.get("cover")
            cover_path = None

            if cover_file and cover_file.filename != "":
                filename = secure_filename(cover_file.filename)
                save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                cover_file.save(save_path)
                # Store relative path in DB
                cover_path = f"covers/{filename}"

            # Create novel instance
            novel = Novel(
    title=title,
    description=description,
    short_description=description[:200] + "...",  # first 100 chars
    genre=genre,
    cover=cover_path
)

            # Optionally, you can add author & genre fields to Novel model if you want
            # For now, you can store them in description or later expand DB

            try:
                db.session.add(novel)
                db.session.commit()
                success = "Novel added successfully!"
            except Exception as e:
                db.session.rollback()
                error = f"Error adding novel: {str(e)}"

    return render_template("add_novel.html", error=error, success=success)


@app.route("/admin/chapters/<int:novel_id>")
def manage_chapters(novel_id):
    if not session.get("is_admin"):
        return redirect("/login")

    novel = Novel.query.get_or_404(novel_id)
    chapters = Chapter.query.filter_by(novel_id=novel.id).all()

    return render_template(
        "manage_chapters.html",
        novel=novel,
        chapters=chapters
    )
@app.route("/admin/add_chapter/<int:novel_id>", methods=["GET", "POST"])
def add_chapter(novel_id):
    if not session.get("is_admin"):
        return redirect("/login")

    novel = Novel.query.get_or_404(novel_id)

    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        status = request.form.get("status", "published")

        if not title or not content:
            error = "Title and content are required"
            return render_template(
                "add_chapter.html",
                novel=novel,
                error=error
            )

        chapter = Chapter(
            novel_id=novel.id,
            title=title,
            content=content,
            status=status
        )

        db.session.add(chapter)
        db.session.commit()

        return redirect(url_for("manage_chapters", novel_id=novel.id))

    return render_template("add_chapter.html", novel=novel)


# -------- STATIC PAGES --------
@app.route("/about")
def about():
    return render_template("about.html")
@app.route("/contact")
def contact():
    return render_template("contact.html")
@app.route("/privacy")
def privacy():
    return render_template("privacy.html")
@app.route("/terms")
def terms():
    return render_template("terms.html")
@app.route("/delete_chapter/<int:chapter_id>", methods=["POST"])
def delete_chapter(chapter_id):
    if not session.get("is_admin"):
        return redirect(url_for("login"))

    chapter = Chapter.query.get_or_404(chapter_id)
    novel_id = chapter.novel_id  # Remember which novel it belongs to
    db.session.delete(chapter)
    db.session.commit()
    return redirect(url_for("manage_chapters", novel_id=novel_id))

@app.route("/edit_chapter/<int:chapter_id>", methods=["GET", "POST"])
def edit_chapter(chapter_id):
    if not session.get("is_admin"):
        return redirect(url_for("login"))

    chapter = Chapter.query.get_or_404(chapter_id)

    if request.method == "POST":
        chapter.title = request.form["title"]
        chapter.content = request.form["content"]
        db.session.commit()
        return redirect(url_for("manage_chapters", novel_id=chapter.novel_id))

    return render_template("edit_chapter.html", chapter=chapter)

@app.route("/delete-novel/<int:novel_id>", methods=["POST"])
def delete_novel(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    db.session.delete(novel)
    db.session.commit()
    flash("Novel deleted successfully!", "success")
    return redirect(url_for("admin"))
@app.route("/edit_novel/<int:novel_id>", methods=["GET", "POST"])
def edit_novel(novel_id):
    novel = Novel.query.get_or_404(novel_id)

    if request.method == "POST":
        novel.title = request.form["title"]
        novel.description = request.form["description"]
        db.session.commit()
        flash("Novel updated successfully!", "success")
        return redirect(url_for("admin"))

    return render_template("edit_novel.html", novel=novel)

@app.route("/novel/<int:novel_id>/chapter/<int:chapter_id>")
def read_chapter(novel_id, chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    novel = Novel.query.get_or_404(novel_id)

    chapters = Chapter.query.filter_by(
        novel_id=novel.id,
        status="published"
    ).order_by(Chapter.id.asc()).all()

    index = chapters.index(chapter)

    prev_chapter = chapters[index - 1] if index > 0 else None
    next_chapter = chapters[index + 1] if index < len(chapters) - 1 else None

    chapter.views += 1
    db.session.commit()

    return render_template(
        "read_chapter.html",
        chapter=chapter,
        novel=novel,
        prev_chapter=prev_chapter,
        next_chapter=next_chapter
    )
@app.route('/novel/<int:novel_id>')
def read_novel(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    return render_template('novel_description.html', novel=novel)



if __name__ == "__main__":
    app.run(debug=True)
