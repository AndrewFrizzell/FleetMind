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
            complete_work_order,
            get_active_checklist_items,
            create_inspection,
            get_master_checklist_items,
            get_machine_checklist,
            add_item_to_machine_checklist,
            remove_item_from_machine_checklist,
            get_machine_by_id,
            get_open_work_orders_for_machine,
            get_recent_inspections_for_machine,
            get_inspections_by_user,
            get_all_inspections,
            create_machine,
            get_all_work_orders

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

@app.route("/machines/<int:machine_id>/inspect", methods=["GET", "POST"])
@login_required
def new_inspection(machine_id):
    conn = get_connection()

    machine = get_machine_by_id(conn, machine_id)

    if machine is None:
        conn.close()
        return "Machine not found", 404

    checklist_items = get_machine_checklist(conn, machine_id)

    if request.method == "POST":
        notes = request.form.get("notes") or ""

        results = {}

        for item in checklist_items:
            field_name = f"item_{item['master_item_id']}"
            passed_value = request.form.get(field_name)

            results[item["name"]] = passed_value == "pass"

        create_inspection(
            conn,
            machine_id=machine_id,
            operator_id=session["user_id"],
            results=results,
            notes=notes
        )

        conn.close()
        flash("Inspection submitted.")
        return redirect(url_for("machine_profile", machine_id=machine_id))

    conn.close()

    return render_template(
        "inspection_form.html",
        user=session,
        machine=machine,
        checklist_items=checklist_items
    )

@app.route("/manager/machines/<int:machine_id>/checklist", methods=["GET"])
@login_required
def manage_machine_checklist(machine_id):
    if session.get("role") != "equipment_manager":
        return "Forbidden", 403
    
    conn = get_connection()

    master_items = get_master_checklist_items(conn)
    machine_items = get_machine_checklist(conn, machine_id)

    conn.close()

    return render_template(
        "machine_checklist.html",
        user=session,
        machine_id=machine_id,
        master_items=master_items,
        machine_items=machine_items
    )

@app.route("/manager/machines/<int:machine_id>/checklist/add", methods=["POST"])
@login_required
def add_machine_checklist_item(machine_id):
    if session.get("role") != "equipment_manager":
        return "Forbidden", 403

    master_item_id = request.form.get("master_item_id")

    conn = get_connection()
    add_item_to_machine_checklist(conn, machine_id, int(master_item_id))

    return redirect(url_for("manage_machine_checklist", machine_id=machine_id))

@app.route("/manager/machine-checklist/remove", methods=["POST"])
@login_required
def remove_machine_checklist_item():
    if session.get("role") != "equipment_manager":
        return "Forbidden", 403
    
    machine_checklist_item_id = request.form.get("machine_checklist_item_id")
    machine_id = request.form.get("machine_id")

    conn = get_connection()
    remove_item_from_machine_checklist(conn, int(machine_checklist_item_id))
    conn.close()

    return redirect(url_for("manage_machine_checklist", machine_id=int(machine_id)))

@app.route("/machines/<int:machine_id>")
@login_required
def machine_profile(machine_id):

    conn = get_connection()

    machine = get_machine_by_id(conn, machine_id)

    if machine is None:
        conn.close()
        return "Machine not found", 404
    
    open_work_orders = get_open_work_orders_for_machine(conn, machine_id)
    recent_inspections = get_recent_inspections_for_machine(conn, machine_id)
    machine_checklist = get_machine_checklist(conn, machine_id)
    conn.close()

    return render_template(
        "machine_profile.html",
        user=session,
        machine=machine,
        open_work_orders=open_work_orders,
        recent_inspections=recent_inspections,
        machine_checklist=machine_checklist
    )

@app.route("/machines")
@login_required
def machines():
    conn = get_connection()
    machines = get_all_machines(conn)
    conn.close()

    return render_template(
        "machines.html",
        user=session,
        machines=machines
    )

@app.route("/inspections")
@login_required
def inspections():
    conn = get_connection()

    if session.get("role") == "operator":
        inspection = get_inspections_by_user(conn, session["user_id"])
    else:
        inspections = get_all_inspections(conn)

    conn.close()

    return render_template(
        "inspections.html",
        user=session,
        inspections=inspections
    )

@app.route("/manager/machines/add", methods=["GET", "POST"])
@login_required
def add_machine():
    if session.get("role") != "equipment_manager":
        return "Forbidden", 403
    
    if request.method == "POST":
        unit_number = request.form.get("unit_number") or ""
        department = request.form.get("department") or ""
        serial_number = request.form.get("serial_number") or ""
        vin_number = request.form.get("vin_number") or ""
        machine_type = request.form.get("type") or ""
        make = request.form.get("make") or ""
        model = request.form.get("model") or ""
        year = request.form.get("year") or None
        meter_type = request.form.get("meter_type") or "hours"
        current_meter_reading = request.form.get("current_meter_reading") or 0
        status = request.form.get("status") or "active"

        if year:
            year = int(year)
        
        current_meter_reading = float(current_meter_reading)
        
        conn = get_connection()

        try:
            machine_id = create_machine(
                    conn,
                    unit_number=unit_number,
                    department=department,
                    serial_number=serial_number,
                    vin_number=vin_number,
                    machine_type=machine_type,
                    make=make,
                    model=model,
                    year=year,
                    meter_type=meter_type,
                    current_meter_reading=current_meter_reading,
                    status=status
                )
            
            flash("Machine added.")
            return redirect(url_for("machine_profile", machine_id=machine_id))
        
        except Exception as e:
            conn.rollback()
            print("Add MACHINE ERROR", e)
            flash(f"Error adding machine: {e}")
            return redirect(url_for("add_machine"))
        
        finally:
            conn.close()
        
    return render_template("add_machine.html", user=session)

@app.route("/manager/work-orders")
@login_required
def manager_work_orders():

    if session.get("role") != "equipment_manager":
        flash("you do not have permission to view that page.")
        return redirect(url_for("dashboard"))
    
    conn= get_connection()

    try:
        work_orders = get_all_work_orders(conn)

        return render_template(
            "work_orders.html",
            work_orders=work_orders,
            role=session.get("role")
        )
    
    finally:
        conn.close()



if __name__ == "__main__":
    #run from /web with python app.py
    app.run(debug=True)