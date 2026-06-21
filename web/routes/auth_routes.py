from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from fleetmind_db import get_connection

auth_bp = Blueprint("auth", __name__)

def get_user_by_email(conn, email: str):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, name, role, email, password_hash, active
        FROM User
        WHERE email = ?
        LIMIT 1
    """, (email,))
    return cursor.fetchone()

@auth_bp.route("/", methods=["GET"])
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("auth.login"))

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        conn = get_connection()
        user = get_user_by_email(conn, email)
        conn.close()

        if not user:
            flash("Invalid email or password.")
            return render_template("login.html")
        
        user_id, name, role, email_db, password_hash, active = user

        if int(active) != 1:
            flash("Account is inactive.")
            return render_template("login.html")
        
        #mvp compare to password_hash column exactly 
        #later store real hashes and verify properly 

        if password != password_hash:
            flash("Invalid email or password.")
            return render_template("login.html")
        
        session["user_id"] = user_id
        session["name"] = name
        session["role"] = role
        session["email"] = email_db

        return redirect(url_for("dashboard"))
    
    return render_template("login.html")

@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))