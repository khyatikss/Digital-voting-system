import os
import re  # For ID validation
import uuid
from datetime import datetime
from typing import List, Optional

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


# Base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass


app = Flask(__name__)
app.config["SECRET_KEY"] = "your-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///voting.db"
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload
app.config["ID_VERIFICATION_REQUIRED"] = True  # Enable ID verification

# Ensure upload directory exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "id_proofs"), exist_ok=True)

# Initialize SQLAlchemy with the app
db = SQLAlchemy(model_class=Base)
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


# Models
class User(db.Model, UserMixin):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(200), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    votes: Mapped[List["Vote"]] = relationship(back_populates="voter", cascade="all, delete-orphan")

    # ID verification fields
    id_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    id_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    id_proof_image: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Candidate(db.Model):
    __tablename__ = "candidate"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    party: Mapped[str] = mapped_column(String(100), nullable=False)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    votes: Mapped[List["Vote"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")


class Vote(db.Model):
    __tablename__ = "vote"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    confirmation_code: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid.uuid4()), unique=True)
    voter: Mapped["User"] = relationship(back_populates="votes")
    candidate: Mapped["Candidate"] = relationship(back_populates="votes")


class Election(db.Model):
    __tablename__ = "election"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# Helper functions for ID verification
def validate_aadhaar(aadhaar_number):
    """Validate Aadhaar number format (12 digits)"""
    pattern = re.compile(r"^\d{12}$")
    return bool(pattern.match(aadhaar_number))


def validate_voter_id(voter_id):
    """Validate Voter ID format (typically 10 characters)"""
    pattern = re.compile(r"^[A-Z]{3}\d{7}$")
    return bool(pattern.match(voter_id))


def validate_pan(pan_number):
    """Validate PAN card format (10 characters: 5 letters, 4 numbers, 1 letter)"""
    pattern = re.compile(r"^[A-Z]{5}\d{4}[A-Z]{1}$")
    return bool(pattern.match(pan_number))


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Routes
@app.route("/")
def index():
    active_election = db.session.query(Election).filter_by(is_active=True).first()
    candidates = db.session.query(Candidate).all()
    return render_template("index.html", candidates=candidates, election=active_election)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # ID verification fields
        id_type = request.form.get("id_type")
        id_number = request.form.get("id_number")

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("register"))

        existing_user = db.session.query(User).filter_by(username=username).first()
        if existing_user:
            flash("Username already exists!", "danger")
            return redirect(url_for("register"))

        existing_email = db.session.query(User).filter_by(email=email).first()
        if existing_email:
            flash("Email already registered!", "danger")
            return redirect(url_for("register"))

        # Validate ID number based on type
        if app.config["ID_VERIFICATION_REQUIRED"]:
            if id_type == "aadhaar":
                if not validate_aadhaar(id_number):
                    flash("Invalid Aadhaar number! Must be 12 digits.", "danger")
                    return redirect(url_for("register"))
            elif id_type == "voter_id":
                if not validate_voter_id(id_number):
                    flash("Invalid Voter ID format!", "danger")
                    return redirect(url_for("register"))
            elif id_type == "pan":
                if not validate_pan(id_number):
                    flash("Invalid PAN card format!", "danger")
                    return redirect(url_for("register"))

            # Check if ID is already registered
            existing_id = db.session.query(User).filter_by(id_type=id_type, id_number=id_number).first()
            if existing_id:
                flash(f"This {id_type.upper()} is already registered!", "danger")
                return redirect(url_for("register"))

            # Handle ID proof image upload
            id_proof_image = None
            if "id_proof" in request.files:
                id_proof = request.files["id_proof"]
                if id_proof.filename != "":
                    id_proof_filename = secure_filename(f"{id_type}_{id_number}_{uuid.uuid4()}.jpg")
                    id_proof_path = os.path.join(app.config["UPLOAD_FOLDER"], "id_proofs", id_proof_filename)
                    id_proof.save(id_proof_path)
                    id_proof_image = os.path.join("id_proofs", id_proof_filename)

        hashed_password = generate_password_hash(password, method="scrypt")
        new_user = User(
            username=username,
            email=email,
            password=hashed_password,
            id_type=id_type,
            id_number=id_number,
            id_proof_image=id_proof_image,
            is_verified=False,  # Admin needs to verify
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! Your ID verification is pending. Please wait for admin approval.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", id_verification_required=app.config["ID_VERIFICATION_REQUIRED"])


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = db.session.query(User).filter_by(username=username).first()

        if not user or not check_password_hash(user.password, password):
            flash("Please check your login details and try again.", "danger")
            return redirect(url_for("login"))

        # Check if user is verified (except for admin)
        if app.config["ID_VERIFICATION_REQUIRED"] and not user.is_admin and not user.is_verified:
            flash("Your account is pending verification. Please wait for admin approval.", "warning")
            return redirect(url_for("login"))

        login_user(user)

        if user.is_admin:
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.is_admin:
        return redirect(url_for("admin_dashboard"))

    # Check if user is verified
    if app.config["ID_VERIFICATION_REQUIRED"] and not current_user.is_verified:
        flash("Your account is pending verification. Please wait for admin approval.", "warning")
        return render_template("verification_pending.html")

    active_election = db.session.query(Election).filter_by(is_active=True).first()
    candidates = db.session.query(Candidate).all()

    # Check if user has already voted
    user_vote = db.session.query(Vote).filter_by(user_id=current_user.id).first()

    return render_template(
        "dashboard.html",
        candidates=candidates,
        election=active_election,
        has_voted=user_vote is not None,
        vote=user_vote,
    )


@app.route("/vote/<int:candidate_id>", methods=["POST"])
@login_required
def vote(candidate_id):
    # Check if user is verified
    if app.config["ID_VERIFICATION_REQUIRED"] and not current_user.is_verified:
        flash("Your account is pending verification. Please wait for admin approval.", "warning")
        return redirect(url_for("dashboard"))

    # Check if user has already voted
    existing_vote = db.session.query(Vote).filter_by(user_id=current_user.id).first()
    if existing_vote:
        flash("You have already voted!", "danger")
        return redirect(url_for("dashboard"))

    # Check if candidate exists
    candidate = db.session.get(Candidate, candidate_id)
    if not candidate:
        flash("Candidate not found!", "danger")
        return redirect(url_for("dashboard"))

    # Create new vote
    new_vote = Vote(user_id=current_user.id, candidate_id=candidate.id)
    db.session.add(new_vote)
    db.session.commit()

    flash(f"Vote successful! Your confirmation code is: {new_vote.confirmation_code}", "success")
    return redirect(url_for("vote_confirmation", vote_id=new_vote.id))


@app.route("/vote/confirmation/<int:vote_id>")
@login_required
def vote_confirmation(vote_id):
    vote = db.session.get(Vote, vote_id)
    if not vote:
        flash("Vote not found!", "danger")
        return redirect(url_for("dashboard"))

    # Ensure the vote belongs to the current user
    if vote.user_id != current_user.id:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("dashboard"))

    candidate = db.session.get(Candidate, vote.candidate_id)

    return render_template("confirmation.html", vote=vote, candidate=candidate)


# Admin routes
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("dashboard"))

    candidates = db.session.query(Candidate).all()
    elections = db.session.query(Election).all()
    total_voters = db.session.query(User).filter_by(is_admin=False).count()
    total_votes = db.session.query(Vote).count()

    # Count pending verifications
    pending_verifications = db.session.query(User).filter_by(is_verified=False, is_admin=False).count()

    return render_template(
        "admin/dashboard.html",
        candidates=candidates,
        elections=elections,
        total_voters=total_voters,
        total_votes=total_votes,
        pending_verifications=pending_verifications,
    )


@app.route("/admin/candidates", methods=["GET"])
@login_required
def admin_candidates():
    if not current_user.is_admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("dashboard"))

    candidates = db.session.query(Candidate).all()
    return render_template("admin/candidates.html", candidates=candidates)


@app.route("/admin/candidates/add", methods=["GET", "POST"])
@login_required
def add_candidate():
    if not current_user.is_admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name")
        party = request.form.get("party")
        bio = request.form.get("bio")

        # Handle image upload
        image_filename = None
        if "image" in request.files:
            image = request.files["image"]
            if image.filename != "":
                image_filename = secure_filename(image.filename)
                image_path = os.path.join(app.config["UPLOAD_FOLDER"], image_filename)
                image.save(image_path)

        new_candidate = Candidate(name=name, party=party, bio=bio, image=image_filename)
        db.session.add(new_candidate)
        db.session.commit()

        flash("Candidate added successfully!", "success")
        return redirect(url_for("admin_candidates"))

    return render_template("admin/add_candidate.html")


@app.route("/admin/candidates/edit/<int:candidate_id>", methods=["GET", "POST"])
@login_required
def edit_candidate(candidate_id):
    if not current_user.is_admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("dashboard"))

    candidate = db.session.get(Candidate, candidate_id)
    if not candidate:
        flash("Candidate not found!", "danger")
        return redirect(url_for("admin_candidates"))

    if request.method == "POST":
        candidate.name = request.form.get("name")
        candidate.party = request.form.get("party")
        candidate.bio = request.form.get("bio")

        # Handle image upload
        if "image" in request.files:
            image = request.files["image"]
            if image.filename != "":
                image_filename = secure_filename(image.filename)
                image_path = os.path.join(app.config["UPLOAD_FOLDER"], image_filename)
                image.save(image_path)

                # Delete old image if exists
                if candidate.image:
                    old_image_path = os.path.join(app.config["UPLOAD_FOLDER"], candidate.image)
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)

                candidate.image = image_filename

        db.session.commit()
        flash("Candidate updated successfully!", "success")
        return redirect(url_for("admin_candidates"))

    return render_template("admin/edit_candidate.html", candidate=candidate)


@app.route("/admin/candidates/delete/<int:candidate_id>", methods=["POST"])
@login_required
def delete_candidate(candidate_id):
    if not current_user.is_admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("dashboard"))

    candidate = db.session.get(Candidate, candidate_id)
    if not candidate:
        flash("Candidate not found!", "danger")
        return redirect(url_for("admin_candidates"))

    # Delete candidate image if exists
    if candidate.image:
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], candidate.image)
        if os.path.exists(image_path):
            os.remove(image_path)

    db.session.delete(candidate)
    db.session.commit()

    flash("Candidate deleted successfully!", "success")
    return redirect(url_for("admin_candidates"))


@app.route("/admin/results")
@login_required
def admin_results():
    if not current_user.is_admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("dashboard"))

    # Get vote counts for each candidate
    candidates = db.session.query(Candidate).all()
    results = []

    for candidate in candidates:
        vote_count = db.session.query(Vote).filter_by(candidate_id=candidate.id).count()
        results.append({"candidate": candidate, "votes": vote_count})

    # Sort by vote count (descending)
    results.sort(key=lambda x: x["votes"], reverse=True)

    total_votes = db.session.query(Vote).count()

    return render_template("admin/results.html", results=results, total_votes=total_votes)


@app.route("/admin/elections", methods=["GET"])
@login_required
def admin_elections():
    if not current_user.is_admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("dashboard"))

    elections = db.session.query(Election).all()
    return render_template("admin/elections.html", elections=elections)


@app.route("/admin/elections/add", methods=["GET", "POST"])
@login_required
def add_election():
    if not current_user.is_admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        start_date = datetime.strptime(request.form.get("start_date"), "%Y-%m-%dT%H:%M")
        end_date = datetime.strptime(request.form.get("end_date"), "%Y-%m-%dT%H:%M")
        is_active = "is_active" in request.form

        # If making this election active, deactivate all other elections
        if is_active:
            active_elections = db.session.query(Election).filter_by(is_active=True).all()
            for election in active_elections:
                election.is_active = False

        new_election = Election(
            title=title, description=description, start_date=start_date, end_date=end_date, is_active=is_active
        )

        db.session.add(new_election)
        db.session.commit()

        flash("Election added successfully!", "success")
        return redirect(url_for("admin_elections"))

    return render_template("admin/add_election.html")


@app.route("/admin/elections/edit/<int:election_id>", methods=["GET", "POST"])
@login_required
def edit_election(election_id):
    if not current_user.is_admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("dashboard"))

    election = db.session.get(Election, election_id)
    if not election:
        flash("Election not found!", "danger")
        return redirect(url_for("admin_elections"))

    if request.method == "POST":
        election.title = request.form.get("title")
        election.description = request.form.get("description")
        election.start_date = datetime.strptime(request.form.get("start_date"), "%Y-%m-%dT%H:%M")
        election.end_date = datetime.strptime(request.form.get("end_date"), "%Y-%m-%dT%H:%M")
        new_is_active = "is_active" in request.form

        # If making this election active, deactivate all other elections
        if new_is_active and not election.is_active:
            active_elections = db.session.query(Election).filter_by(is_active=True).all()
            for active_election in active_elections:
                active_election.is_active = False

        election.is_active = new_is_active

        db.session.commit()
        flash("Election updated successfully!", "success")
        return redirect(url_for("admin_elections"))

    return render_template("admin/edit_election.html", election=election)


@app.route("/admin/elections/delete/<int:election_id>", methods=["POST"])
@login_required
def delete_election(election_id):
    if not current_user.is_admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("dashboard"))

    election = db.session.get(Election, election_id)
    if not election:
        flash("Election not found!", "danger")
        return redirect(url_for("admin_elections"))

    db.session.delete(election)
    db.session.commit()

    flash("Election deleted successfully!", "success")
    return redirect(url_for("admin_elections"))


@app.route("/admin/users")
@login_required
def admin_users():
    if not current_user.is_admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("dashboard"))

    users = db.session.query(User).all()
    # Add this line to count pending verifications
    pending_verifications = db.session.query(User).filter_by(is_verified=False, is_admin=False).count()
    return render_template("admin/users.html", users=users, pending_verifications=pending_verifications)


@app.route("/admin/make_admin/<int:user_id>", methods=["POST"])
@login_required
def make_admin(user_id):
    if not current_user.is_admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("dashboard"))

    user = db.session.get(User, user_id)
    if not user:
        flash("User not found!", "danger")
        return redirect(url_for("admin_users"))

    user.is_admin = True
    db.session.commit()
    flash(f"{user.username} is now an admin!", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/verify_user/<int:user_id>", methods=["POST"])
@login_required
def verify_user(user_id):
    if not current_user.is_admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("dashboard"))

    user = db.session.get(User, user_id)
    if not user:
        flash("User not found!", "danger")
        return redirect(url_for("admin_users"))

    user.is_verified = True
    db.session.commit()

    flash(f"{user.username}'s ID has been verified!", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/reject_user/<int:user_id>", methods=["POST"])
@login_required
def reject_user(user_id):
    if not current_user.is_admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("dashboard"))

    user = db.session.get(User, user_id)
    if not user:
        flash("User not found!", "danger")
        return redirect(url_for("admin_users"))

    # Delete ID proof image if exists
    if user.id_proof_image:
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], user.id_proof_image)
        if os.path.exists(image_path):
            os.remove(image_path)

    # Delete user
    db.session.delete(user)
    db.session.commit()

    flash(f"User {user.username} has been rejected and removed!", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/view_id_proof/<int:user_id>")
@login_required
def view_id_proof(user_id):
    if not current_user.is_admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("dashboard"))

    user = db.session.get(User, user_id)
    if not user or not user.id_proof_image:
        flash("ID proof not found!", "danger")
        return redirect(url_for("admin_users"))

    return render_template("admin/view_id_proof.html", user=user)


@app.route("/admin/pending_verifications")
@login_required
def pending_verifications():
    if not current_user.is_admin:
        flash("Unauthorized access!", "danger")
        return redirect(url_for("dashboard"))

    pending_users = db.session.query(User).filter_by(is_verified=False, is_admin=False).all()
    return render_template("admin/pending_verifications.html", users=pending_users)


@app.route("/verify_vote/<string:confirmation_code>")
def verify_vote(confirmation_code):
    vote = db.session.query(Vote).filter_by(confirmation_code=confirmation_code).first()

    if not vote:
        flash("Invalid confirmation code!", "danger")
        return redirect(url_for("index"))

    candidate = db.session.get(Candidate, vote.candidate_id)
    user = db.session.get(User, vote.user_id)

    return render_template("verify_vote.html", vote=vote, candidate=candidate, user=user)


# Create admin user if not exists
def create_tables_and_admin():
    with app.app_context():
        db.create_all()
        admin = db.session.query(User).filter_by(username="admin").first()
        if not admin:
            hashed_password = generate_password_hash("admin123", method="scrypt")
            admin = User(
                username="admin",
                email="admin@example.com",
                password=hashed_password,
                is_admin=True,
                is_verified=True,  # Admin is always verified
            )
            db.session.add(admin)
            db.session.commit()


# Initialize the database and create admin user
with app.app_context():
    db.create_all()
    create_tables_and_admin()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
