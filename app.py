import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import ensure_default_admin, get_db_connection, init_db

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError(f"SECRET_KEY is missing. Set it in {BASE_DIR / '.env'}.")


init_db()
ensure_default_admin()


def parse_skills(raw_value):
    if not raw_value:
        return []
    values = [item.strip() for item in raw_value.replace(";", ",").split(",") if item.strip()]
    return values


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
    conn.close()
    return user


def current_student(user_id=None):
    student_id = user_id or session.get("user_id")
    if not student_id:
        return None
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT s.*, u.department FROM students s JOIN users u ON u.id = s.user_id WHERE s.user_id = %s",
            (student_id,),
        )
        student = cur.fetchone()
    conn.close()
    return student


def current_company(user_id=None):
    user_id = user_id or session.get("user_id")
    if not user_id:
        return None
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM companies WHERE user_id = %s", (user_id,))
        company = cur.fetchone()
    conn.close()
    return company


def get_company_by_user_id(user_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM companies WHERE user_id = %s", (user_id,))
        company = cur.fetchone()
    conn.close()
    return company


def is_logged_in():
    return bool(session.get("user_id"))


def require_login():
    if not is_logged_in():
        flash("Please log in to continue.", "warning")
        return redirect(url_for("login"))
    return None


def normalize_company_opportunity(row):
    row = dict(row)
    row["skills_required"] = row.get("skills_required") or []
    return row


def calculate_match_score(student, opportunity):
    if not student or not opportunity:
        return 0

    score = 0
    student_skills = set(student.get("skills") or [])
    required_skills = set(opportunity.get("skills_required") or [])
    common_skills = len(student_skills & required_skills)

    if student.get("department") == opportunity.get("department"):
        score += 30
    elif opportunity.get("department") == "All":
        score += 20

    if float(student.get("cgpa", 0) or 0) >= float(opportunity.get("min_cgpa", 0) or 0):
        score += 35
    else:
        score -= 20

    score += common_skills * 15
    return score


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
        conn.close()

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")

        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["name"] = user["name"]

        flash(f"Welcome back, {user['name']}.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        role = request.form.get("role")
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        department = request.form.get("department", "").strip()
        phone = request.form.get("phone", "").strip()

        if not all([name, email, password]):
            flash("Please complete all required fields.", "danger")
            return render_template("register.html")

        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                conn.close()
                flash("An account with this email already exists.", "warning")
                return render_template("register.html")

            password_hash = generate_password_hash(password)
            cur.execute(
                """
                INSERT INTO users (name, email, password_hash, role, department, phone)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (name, email, password_hash, role, department or None, phone or None),
            )
            user_id = cur.fetchone()["id"]

            if role == "student":
                cgpa = float(request.form.get("cgpa", 0) or 0)
                year = request.form.get("year", "3rd Year")
                skills = parse_skills(request.form.get("skills", ""))
                bio = request.form.get("bio", "").strip()
                resume_url = request.form.get("resume_url", "").strip()
                cur.execute(
                    """
                    INSERT INTO students (user_id, cgpa, year_of_study, skills, bio, resume_url)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, cgpa, year, skills, bio or None, resume_url or None),
                )
            elif role == "company":
                company_name = request.form.get("company_name", "").strip()
                industry = request.form.get("industry", "").strip()
                website = request.form.get("website", "").strip()
                location = request.form.get("location", "").strip()
                about = request.form.get("about", "").strip()
                cur.execute(
                    """
                    INSERT INTO companies (user_id, company_name, industry, website, location, about)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, company_name, industry or None, website or None, location or None, about or None),
                )
            elif role == "admin":
                conn.close()
                flash("Admin accounts are created only through the system administrator.", "warning")
                return redirect(url_for("login"))

        conn.commit()
        conn.close()

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    if not is_logged_in():
        flash("Please log in to continue.", "warning")
        return redirect(url_for("login"))

    role = session.get("role")
    if role == "student":
        return redirect(url_for("student_dashboard"))
    if role == "company":
        return redirect(url_for("company_dashboard"))
    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    session.clear()
    return redirect(url_for("login"))


@app.route("/student/dashboard")
def student_dashboard():
    user = current_user()
    if not user or user["role"] != "student":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    student = current_student(user["id"])
    if not student:
        flash("Complete your profile first.", "warning")
        return redirect(url_for("student_profile"))

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM opportunities WHERE is_active = TRUE ORDER BY created_at DESC"
        )
        opportunities = cur.fetchall()

        cur.execute(
            "SELECT o.*, a.status, a.applied_at FROM applications a JOIN opportunities o ON o.id = a.opportunity_id WHERE a.student_id = %s ORDER BY a.applied_at DESC",
            (user["id"],),
        )
        applications = cur.fetchall()

        cur.execute(
            "SELECT * FROM certificates WHERE student_id = %s ORDER BY issue_date DESC",
            (user["id"],),
        )
        certificates = cur.fetchall()

    conn.close()

    for opportunity in opportunities:
        opportunity["skills_required"] = opportunity.get("skills_required") or []
        opportunity["match_score"] = calculate_match_score(student, opportunity)

    recommended = sorted(opportunities, key=lambda item: item["match_score"], reverse=True)[:5]

    return render_template(
        "student_dashboard.html",
        user=user,
        student=student,
        opportunities=opportunities,
        recommended=recommended,
        applications=applications,
        certificates=certificates,
    )


@app.route("/student/profile", methods=["GET", "POST"])
def student_profile():
    user = current_user()
    if not user or user["role"] != "student":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    student = current_student(user["id"])
    if request.method == "POST":
        department = request.form.get("department", "").strip()
        cgpa = float(request.form.get("cgpa", 0) or 0)
        year = request.form.get("year", "3rd Year")
        bio = request.form.get("bio", "").strip()
        resume_url = request.form.get("resume_url", "").strip()
        skills = parse_skills(request.form.get("skills", ""))

        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO students (user_id, cgpa, year_of_study, skills, bio, resume_url)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    cgpa = EXCLUDED.cgpa,
                    year_of_study = EXCLUDED.year_of_study,
                    skills = EXCLUDED.skills,
                    bio = EXCLUDED.bio,
                    resume_url = EXCLUDED.resume_url
                """,
                (user["id"], cgpa, year, skills, bio or None, resume_url or None),
            )
            cur.execute(
                "UPDATE users SET department = %s WHERE id = %s",
                (department or user.get("department"), user["id"]),
            )
        conn.commit()
        conn.close()
        flash("Your profile has been updated.", "success")
        return redirect(url_for("student_profile"))

    if not student:
        student = {"cgpa": 0.0, "year_of_study": "3rd Year", "skills": [], "bio": "", "resume_url": ""}

    return render_template("student_profile.html", user=user, student=student)


@app.route("/student/skills", methods=["GET", "POST"])
def student_skills():
    user = current_user()
    if not user or user["role"] != "student":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    student = current_student(user["id"])
    if request.method == "POST":
        skills = parse_skills(request.form.get("skills", ""))
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO students (user_id, cgpa, year_of_study, skills, bio, resume_url)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id)
                DO UPDATE SET skills = EXCLUDED.skills
                """,
                (user["id"], student["cgpa"] if student else 0.0, student["year_of_study"] if student else "3rd Year", skills, student["bio"] if student else None, student["resume_url"] if student else None),
            )
        conn.commit()
        conn.close()
        flash("Your skills profile has been updated.", "success")
        return redirect(url_for("student_skills"))

    return render_template("skills.html", user=user, student=student)


@app.route("/student/opportunities")
def opportunities():
    user = current_user()
    if not user or user["role"] != "student":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    student = current_student(user["id"])
    if not student:
        flash("Please complete your student profile before exploring opportunities.", "warning")
        return redirect(url_for("student_profile"))

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT o.*, c.company_name FROM opportunities o JOIN companies c ON c.id = o.company_id WHERE o.is_active = TRUE ORDER BY o.created_at DESC"
        )
        opportunities_list = cur.fetchall()

        cur.execute(
            "SELECT opportunity_id FROM applications WHERE student_id = %s",
            (user["id"],),
        )
        applied_ids = {row["opportunity_id"] for row in cur.fetchall()}
    conn.close()

    for opportunity in opportunities_list:
        opportunity["skills_required"] = opportunity.get("skills_required") or []
        opportunity["match_score"] = calculate_match_score(student, opportunity)
        opportunity["already_applied"] = opportunity["id"] in applied_ids

    opportunities_list = sorted(opportunities_list, key=lambda item: item["match_score"], reverse=True)

    return render_template("opportunities.html", user=user, opportunities=opportunities_list, student=student)


@app.route("/student/opportunity/<int:opportunity_id>")
def opportunity_details(opportunity_id):
    user = current_user()
    if not user or user["role"] != "student":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT o.*, c.company_name, c.location AS company_location, c.website, c.industry FROM opportunities o JOIN companies c ON c.id = o.company_id WHERE o.id = %s",
            (opportunity_id,),
        )
        opportunity = cur.fetchone()

        cur.execute(
            "SELECT * FROM applications WHERE student_id = %s AND opportunity_id = %s",
            (user["id"], opportunity_id),
        )
        application = cur.fetchone()
    conn.close()

    if not opportunity:
        return render_template("error.html", message="Opportunity not found."), 404

    opportunity["skills_required"] = opportunity.get("skills_required") or []
    return render_template("opportunity_details.html", user=user, opportunity=opportunity, application=application)


@app.route("/student/apply/<int:opportunity_id>", methods=["POST"])
def apply_to_opportunity(opportunity_id):
    user = current_user()
    if not user or user["role"] != "student":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    cover_letter = request.form.get("cover_letter", "").strip()
    student = current_student(user["id"])
    if not student:
        flash("Complete your profile before applying.", "warning")
        return redirect(url_for("student_profile"))

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM opportunities WHERE id = %s AND is_active = TRUE",
            (opportunity_id,),
        )
        opportunity = cur.fetchone()
        if not opportunity:
            conn.close()
            flash("Opportunity not found or no longer active.", "warning")
            return redirect(url_for("opportunities"))

        cur.execute(
            "SELECT * FROM applications WHERE student_id = %s AND opportunity_id = %s",
            (user["id"], opportunity_id),
        )
        if cur.fetchone():
            conn.close()
            flash("You have already applied for this opportunity.", "info")
            return redirect(url_for("opportunities"))

        cur.execute(
            "INSERT INTO applications (student_id, opportunity_id, cover_letter, status) VALUES (%s, %s, %s, 'applied')",
            (user["id"], opportunity_id, cover_letter or None),
        )
    conn.commit()
    conn.close()
    flash("Application submitted successfully.", "success")
    return redirect(url_for("applications"))


@app.route("/student/applications")
def applications():
    user = current_user()
    if not user or user["role"] != "student":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.*, o.title, o.company_id, c.company_name, o.location, o.type, o.min_cgpa
            FROM applications a
            JOIN opportunities o ON o.id = a.opportunity_id
            JOIN companies c ON c.id = o.company_id
            WHERE a.student_id = %s
            ORDER BY a.applied_at DESC
            """,
            (user["id"],),
        )
        applications_list = cur.fetchall()
    conn.close()
    return render_template("applications.html", user=user, applications=applications_list)


@app.route("/student/certificates", methods=["GET", "POST"])
def certificates():
    user = current_user()
    if not user or user["role"] != "student":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        issuer = request.form.get("issuer", "").strip()
        issue_date = request.form.get("issue_date")
        certificate_url = request.form.get("certificate_url", "").strip()

        if not all([title, issuer, issue_date]):
            flash("Please complete all certificate fields.", "danger")
            return redirect(url_for("certificates"))

        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO certificates (student_id, title, issuer, issue_date, certificate_url) VALUES (%s, %s, %s, %s, %s)",
                (user["id"], title, issuer, issue_date, certificate_url or None),
            )
        conn.commit()
        conn.close()
        flash("Certificate added successfully.", "success")
        return redirect(url_for("certificates"))

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM certificates WHERE student_id = %s ORDER BY issue_date DESC", (user["id"],))
        certificate_list = cur.fetchall()
    conn.close()

    return render_template("certificates.html", user=user, certificates=certificate_list)


@app.route("/company/dashboard")
def company_dashboard():
    user = current_user()
    if not user or user["role"] != "company":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    company = get_company_by_user_id(user["id"])
    if not company:
        flash("Create your company profile first.", "warning")
        return redirect(url_for("register"))

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM opportunities WHERE company_id = %s ORDER BY created_at DESC",
            (company["id"],),
        )
        opportunities = cur.fetchall()

        cur.execute(
            "SELECT COUNT(*) AS total_applications FROM applications a JOIN opportunities o ON o.id = a.opportunity_id WHERE o.company_id = %s",
            (company["id"],),
        )
        total_applications = cur.fetchone()["total_applications"]

        cur.execute(
            "SELECT COUNT(*) AS total_opportunities FROM opportunities WHERE company_id = %s",
            (company["id"],),
        )
        total_opportunities = cur.fetchone()["total_opportunities"]

        cur.execute(
            "SELECT COUNT(*) AS shortlisted FROM applications a JOIN opportunities o ON o.id = a.opportunity_id WHERE o.company_id = %s AND a.status = 'shortlisted'",
            (company["id"],),
        )
        shortlisted = cur.fetchone()["shortlisted"]
    conn.close()

    return render_template(
        "company_dashboard.html",
        user=user,
        company=company,
        opportunities=opportunities,
        total_applications=total_applications,
        total_opportunities=total_opportunities,
        shortlisted=shortlisted,
    )


@app.route("/company/opportunity/add", methods=["GET", "POST"])
def add_opportunity():
    user = current_user()
    if not user or user["role"] != "company":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    company = get_company_by_user_id(user["id"])
    if not company:
        flash("Create your company profile first.", "warning")
        return redirect(url_for("register"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        department = request.form.get("department", "All").strip()
        eligibility = request.form.get("eligibility", "").strip()
        min_cgpa = float(request.form.get("min_cgpa", 0) or 0)
        skills_required = parse_skills(request.form.get("skills_required", ""))
        opportunity_type = request.form.get("type", "Internship")
        stipend = request.form.get("stipend", "").strip()
        location = request.form.get("location", "").strip()
        deadline = request.form.get("application_deadline")

        if not all([title, description, deadline]):
            flash("Please complete all required fields.", "danger")
            return render_template("add_opportunity.html", user=user, company=company)

        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO opportunities (company_id, title, description, department, eligibility, min_cgpa, skills_required, type, stipend, location, application_deadline)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    company["id"],
                    title,
                    description,
                    department,
                    eligibility,
                    min_cgpa,
                    skills_required,
                    opportunity_type,
                    stipend or None,
                    location or None,
                    deadline,
                ),
            )
        conn.commit()
        conn.close()
        flash("Opportunity created successfully.", "success")
        return redirect(url_for("company_dashboard"))

    return render_template("add_opportunity.html", user=user, company=company)


@app.route("/company/opportunity/<int:opportunity_id>/edit", methods=["GET", "POST"])
def edit_opportunity(opportunity_id):
    user = current_user()
    if not user or user["role"] != "company":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    company = get_company_by_user_id(user["id"])
    if not company:
        flash("Create your company profile first.", "warning")
        return redirect(url_for("company_dashboard"))

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM opportunities WHERE id = %s AND company_id = %s", (opportunity_id, company["id"]))
        opportunity = cur.fetchone()
    conn.close()

    if not opportunity:
        flash("Opportunity not found.", "warning")
        return redirect(url_for("company_dashboard"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        department = request.form.get("department", "All").strip()
        eligibility = request.form.get("eligibility", "").strip()
        min_cgpa = float(request.form.get("min_cgpa", 0) or 0)
        skills_required = parse_skills(request.form.get("skills_required", ""))
        opportunity_type = request.form.get("type", "Internship")
        stipend = request.form.get("stipend", "").strip()
        location = request.form.get("location", "").strip()
        deadline = request.form.get("application_deadline")

        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE opportunities
                SET title = %s, description = %s, department = %s, eligibility = %s, min_cgpa = %s,
                    skills_required = %s, type = %s, stipend = %s, location = %s, application_deadline = %s
                WHERE id = %s AND company_id = %s
                """,
                (
                    title,
                    description,
                    department,
                    eligibility,
                    min_cgpa,
                    skills_required,
                    opportunity_type,
                    stipend or None,
                    location or None,
                    deadline,
                    opportunity_id,
                    get_company_by_user_id(user["id"])["id"],
                ),
            )
        conn.commit()
        conn.close()
        flash("Opportunity updated successfully.", "success")
        return redirect(url_for("company_dashboard"))

    opportunity["skills_required"] = opportunity.get("skills_required") or []
    return render_template("edit_opportunity.html", user=user, opportunity=opportunity)


@app.route("/company/opportunity/<int:opportunity_id>/applicants")
def applicants(opportunity_id):
    user = current_user()
    if not user or user["role"] != "company":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM opportunities WHERE id = %s AND company_id = %s",
            (opportunity_id, get_company_by_user_id(user["id"])["id"]),
        )
        opportunity = cur.fetchone()

        if opportunity:
            cur.execute(
                """
                SELECT a.*, u.name, u.email, s.cgpa, s.skills, s.year_of_study, s.bio
                FROM applications a
                JOIN students s ON s.user_id = a.student_id
                JOIN users u ON u.id = a.student_id
                WHERE a.opportunity_id = %s
                ORDER BY a.applied_at DESC
                """,
                (opportunity_id,),
            )
            applicants_list = cur.fetchall()
        else:
            applicants_list = []
    conn.close()

    if not opportunity:
        flash("Opportunity not found.", "warning")
        return redirect(url_for("company_dashboard"))

    return render_template("applicants.html", user=user, opportunity=opportunity, applicants=applicants_list)


@app.route("/company/application/<int:application_id>/status", methods=["POST"])
def update_application_status(application_id):
    user = current_user()
    if not user or user["role"] != "company":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    status = request.form.get("status")
    if status not in ["applied", "shortlisted", "rejected", "accepted"]:
        flash("Invalid application status.", "danger")
        return redirect(url_for("company_dashboard"))

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE applications SET status = %s WHERE id = %s AND opportunity_id IN (SELECT id FROM opportunities WHERE company_id = %s)",
            (status, application_id, get_company_by_user_id(user["id"])["id"]),
        )
    conn.commit()
    conn.close()
    flash("Application status updated.", "success")
    return redirect(url_for("company_dashboard"))


@app.route("/admin/dashboard")
def admin_dashboard():
    user = current_user()
    if not user or user["role"] != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS total_students FROM users WHERE role = 'student'")
        total_students = cur.fetchone()["total_students"]

        cur.execute("SELECT COUNT(*) AS total_companies FROM users WHERE role = 'company'")
        total_companies = cur.fetchone()["total_companies"]

        cur.execute("SELECT COUNT(*) AS total_opportunities FROM opportunities WHERE is_active = TRUE")
        total_opportunities = cur.fetchone()["total_opportunities"]

        cur.execute("SELECT COUNT(*) AS total_applications FROM applications")
        total_applications = cur.fetchone()["total_applications"]
    conn.close()

    return render_template(
        "admin_dashboard.html",
        user=user,
        total_students=total_students,
        total_companies=total_companies,
        total_opportunities=total_opportunities,
        total_applications=total_applications,
    )


@app.route("/admin/students")
def manage_students():
    user = current_user()
    if not user or user["role"] != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT u.*, s.cgpa, s.year_of_study, s.skills FROM users u LEFT JOIN students s ON s.user_id = u.id WHERE u.role = 'student' ORDER BY u.name"
        )
        students = cur.fetchall()
    conn.close()
    return render_template("manage_students.html", user=user, students=students)


@app.route("/admin/companies")
def manage_companies():
    user = current_user()
    if not user or user["role"] != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT u.*, c.company_name, c.industry, c.location, c.is_verified FROM users u JOIN companies c ON c.user_id = u.id WHERE u.role = 'company' ORDER BY u.name"
        )
        companies = cur.fetchall()
    conn.close()
    return render_template("manage_companies.html", user=user, companies=companies)


@app.route("/admin/toggle-user/<int:user_id>", methods=["POST"])
def toggle_user_status(user_id):
    user = current_user()
    if not user or user["role"] != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("login"))

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET is_active = NOT is_active WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    flash("User status updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.errorhandler(404)
def page_not_found(error):
    return render_template("error.html", message="The page you requested could not be found."), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template("error.html", message="An unexpected server error occurred."), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
