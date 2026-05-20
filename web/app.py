import os
import sys
# Add project root (fleetmind/) to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, render_template, request, redirect, url_for, session, flash

from fleetmind_db import get_connection
from logic import (
            get_open_work_orders, 
            get_mechanics, 
            get_all_machines, 
            create_mechanic_assignment,
            get_assignments_for_mechanics,
            get_work_orders_for_assignment,
            complete_work_order
)

app = Flask(__name__)
app.secret_key = "dev-secret-change-me" #change this later

def get_user_by_email(conn, email: str):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, name, role, email, password_hash, active
        FROM User
        WHERE email = ?
        LIMIT 1
    """, (email,))
    return cursor.fetchone()

def login_required(view_func):
    from functools import wraps

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper

@app.route("/", methods=["GET"])
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
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

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    role = session.get("role")

    if role == "operator":
        return render_template("dashboard_operator.html", user=session)
    if role == "foreman":
        return render_template("dashboard_foreman.html", user=session)
    if role == "equipment_manager":
        conn = get_connection()
        open_work_orders = get_open_work_orders(conn)
        mechanics = get_mechanics(conn)
        machines = get_all_machines(conn)
        conn.close()

        return render_template(
            "dashboard_manager.html",
            user={
                "name": session.get("name"),
                "role": session.get("role"),
                "email": session.get("email"),
                "user_id": session.get("user_id")
            },
            open_work_orders = open_work_orders,
            mechanics=mechanics, 
            machines=machines
        )
    if role == "mechanic":
        conn = get_connection()
        assignments = get_assignments_for_mechanics(conn, session.get("user_id"))

        assignment_data = []
        for assignment in assignments:
            work_orders = get_work_orders_for_assignment(conn, assignment["assignment_id"])
            assignment_data.append({
                "assignment": assignment,
                "work_orders": work_orders
            })

        conn.close()

        return render_template(
                    "dashboard_mechanic.html", 
                    user=session,
                    assignment_data=assignment_data
        )
    
    #fallback
    return "unknown role", 400

@app.route("/manager/create-assignment", methods=["POST"])
@login_required
def manager_create_assignment():
    if session.get("role") != "equipment_manager":
        return "Forbidden", 403
    
    mechanic_id = request.form.get("mechanic_id")
    work_order_ids = request.form.getlist("work_order_ids")

    if not mechanic_id or not work_order_ids:
        flash("Pick a mechanic and at least one work order.")
        return redirect(url_for("dashboard"))
    
    mechanic_id = int(mechanic_id)
    work_order_ids = [int(x) for x in work_order_ids]

    conn = get_connection()
    try:
        assignment_id = create_mechanic_assignment(conn, mechanic_id, work_order_ids)
        conn.commit()
    except Exception as e:
        conn.rollback()
        flash(f"Error creating assignment: {e}")
        return redirect(url_for("dashboard"))
    finally:
        conn.close()

    flash(f"Created assignment #{assignment_id}.")
    return redirect(url_for("dashboard"))

@app.route("/mechanic/complete-work-order", methods=["POST"])
@login_required
def mechanic_complete_work_order():

    if session.get("role") != "mechanic":
        return "Forbidden", 403
    
    work_order_id = request.form.get("work_order_id")

    if not work_order_id:
        flash("Missing work order.")
        return redirect(url_for("dashboard"))
    
    conn = get_connection()

    try:
        complete_work_order(conn, int(work_order_id))
        flash(f"Work order #{work_order_id} completed.")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}")
    finally:
        conn.close()
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    #run from /web with python app.py
    app.run(debug=True)