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
            get_all_work_orders,
            create_master_checklist_item,
            get_open_inspection_for_machine,
            create_open_inspection,
            save_inspection_items,
            close_inspection,
            update_machine_meter,
            get_machine_current_meter,
            get_open_faults_for_machine,
            get_work_order_by_id,
            add_work_order_comment,
            get_work_order_comments,
            get_work_order_events,
            add_work_order_event,
            get_work_order_timeline,
            get_inspections_for_operator,
            get_operator_machine_list,
            get_jobs_for_foreman,
            get_machines_for_job,
            get_job_by_id,
            get_active_jobs,
            create_job,
            get_machines_available_for_job,
            assign_machine_to_job,
            get_open_work_orders_for_job,
            get_recent_inspections_for_job,
            get_inspection_by_id,
            get_inspection_items,
            update_machine_operational_state,
            remove_machine_from_job,
            get_job_events,
            add_job_event,
            get_machine_unit_number,
            add_work_order_part,
            get_work_order_parts,
            update_work_order_part_status,
            get_work_order_part_by_id,
            get_all_work_order_parts


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
        conn = get_connection()

        operator_inspections = get_inspections_for_operator(
            conn,
            session["user_id"]
        )

        open_inspections = [
            inspection for inspection in operator_inspections
            if inspection["status"] == "open"
        ]

        recent_inspections = operator_inspections[:10]

        machines = get_operator_machine_list(conn)

        conn.close()

        return render_template(
            "dashboard_operator.html",
            user=session,
            open_inspections=open_inspections,
            recent_inspections=recent_inspections,
            machines=machines
        )

    if role == "foreman":
        conn = get_connection()

        jobs = get_jobs_for_foreman(
            conn,
            session["user_id"]
        )

        conn.close()

        return render_template(
            "dashboard_foreman.html",
            user=session,
            jobs=jobs
        )

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

@app.route("/work-orders/<int:work_order_id>")
@login_required
def work_order_detail(work_order_id):
    conn = get_connection()

    work_order = get_work_order_by_id(conn, work_order_id)
    timeline = get_work_order_timeline(conn, work_order_id)
    parts = get_work_order_parts(conn, work_order_id)

    conn.close()

    if work_order is None:
        return "Work order not found", 404
    
    return render_template(
        "work_order_detail.html",
        user=session,
        work_order=work_order,
        timeline=timeline,
        parts=parts
    )

@app.route("/work-orders/<int:work_order_id>/comments/add", methods=["POST"])
@login_required
def add_work_order_comment_route(work_order_id):
    comment = request.form.get("comment", "").strip()

    if not comment:
        flash("Comment cannot be empty.")
        return redirect(url_for("work_order_detail", work_order_id=work_order_id))
    
    conn = get_connection()

    add_work_order_comment(
        conn,
        work_order_id,
        session["user_id"],
        comment
    )

    conn.close()
    flash("Comment added.")
    return redirect(url_for("work_order_detail", work_order_id=work_order_id))

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

        cur = conn.cursor()
        cur.execute("""
            SELECT work_order_id, status, completed_at
            FROM WorkOrder
            WHERE work_order_id = ?
        """, (int(work_order_id),))

        flash(f"Work order #{work_order_id} completed.")
    except Exception as e:
        print(f"error", e)
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

    jobs = get_active_jobs(conn)

    existing_inspection = get_open_inspection_for_machine(conn, machine_id)

    if existing_inspection:
        if existing_inspection["operator_id"] != session["user_id"]:
            conn.close()
            return "This machine already has an open inspection by another operator."

    if request.method == "POST":
        notes = request.form.get("notes") or ""

        meter_row = get_machine_current_meter(conn, machine_id)
        current_meter = meter_row["current_meter_reading"] or 0

        if existing_inspection:
            inspection_id = existing_inspection["inspection_id"]

            inspection_action = request.form.get("inspection_action")
            current_meter_input = request.form.get("current_meter") or None

            if current_meter_input and int(current_meter_input) < current_meter:
                conn.close()
                flash("Meter reading cannot be lower than the machine's current meter reading.")
                return redirect(url_for("new_inspection", machine_id=machine_id))
            
            if current_meter_input:
                update_machine_meter(conn, machine_id, int(current_meter_input))
            
            if inspection_action == "close":
                close_inspection(
                    conn,
                    inspection_id,
                    current_meter_input
                )
        else:
            opening_meter = request.form.get("opening_meter") or None

            if opening_meter and int(opening_meter) < current_meter:
                conn.close()
                flash("Meter reading cannot be lower than the machine's current meter reading.")
                return redirect(url_for("new_inspection", machine_id=machine_id))
            
            if opening_meter:
                update_machine_meter(conn, machine_id, int(opening_meter))

            job_id = request.form.get("job_id") or None

            if job_id:
                job_id = int(job_id)

            inspection = create_open_inspection(
                conn,
                machine_id=machine_id,
                operator_id=session["user_id"],
                opening_meter=opening_meter,
                notes=notes,
                job_id=job_id
            )

            inspection_id = inspection["inspection_id"]

        results = {}

        for item in checklist_items:
            item_id = item["master_item_id"]

            field_name = f"item_{item_id}"
            note_field = f"note_{item_id}"
            decision_field = f"decision_{item_id}"

            passed_value = request.form.get(field_name)
            item_note = request.form.get(note_field, "").strip()
            operator_decision = request.form.get(decision_field)

            results[item["name"]] = {
                "passed": passed_value == "pass",
                "note": item_note,
                "operator_decision": operator_decision
            }

        should_close_due_to_down = any(
            data["operator_decision"] == "down"
            for data in results.values()
        )

        save_inspection_items(
            conn,
            inspection_id,
            machine_id,
            session["user_id"],
            results
        )

        has_faild_items = any(
            data["passed"] == False
            for data in results.values()
        )

        if should_close_due_to_down:
            update_machine_operational_state(
                conn,
                machine_id,
                "down"
            )

            if existing_inspection:
                close_inspection(
                    conn,
                    inspection_id,
                    current_meter_input
                )
            else:
                close_inspection(
                    conn,
                    inspection_id,
                    opening_meter
                )
        
        elif has_faild_items:

            update_machine_operational_state(
                conn,
                machine_id,
                "running_with_faults"
            )

        conn.close()
        flash("Inspection saved.")
        return redirect(url_for("machine_profile", machine_id=machine_id))

    conn.close()

    return render_template(
        "inspection_form.html",
        user=session,
        machine=machine,
        checklist_items=checklist_items,
        existing_inspection=existing_inspection,
        jobs=jobs
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

    selected_item_ids = request.form.getlist("master_item_ids")
    new_item_name = request.form.get("new_item_name", "").strip()
    new_item_description = request.form.get("new_item_description", "").strip()

    conn = get_connection()

    for item_id in selected_item_ids:
        add_item_to_machine_checklist(conn, machine_id, int(item_id))
    
    if new_item_name:
        new_master_item= create_master_checklist_item(
            conn,
            new_item_name,
            new_item_description
        )
        add_item_to_machine_checklist(
            conn,
            machine_id,
            new_master_item["item_id"]
        )
    
    conn.close()


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

    open_faults = get_open_faults_for_machine(conn, machine_id)

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
        machine_checklist=machine_checklist,
        open_faults=open_faults
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
        inspections = get_inspections_by_user(conn, session["user_id"])
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

@app.route("/jobs/<int:job_id>")
@login_required
def job_detail(job_id):

    conn = get_connection()

    job = get_job_by_id(conn, job_id)

    if job is None:
        conn.close()
        return "Job not found", 404
    
    open_work_orders = get_open_work_orders_for_job(conn, job_id)
    recent_inspections = get_recent_inspections_for_job(conn, job_id)
    job_events = get_job_events(conn, job_id)
    machines = get_machines_for_job(conn, job_id)
    unassigned_machines = get_machines_available_for_job(conn, job_id)

    conn.close()

    return render_template (
        "job_detail.html",
        user=session,
        job=job,
        machines=machines,
        unassigned_machines=unassigned_machines,
        open_work_orders=open_work_orders,
        recent_inspections=recent_inspections,
        job_events=job_events
    )

@app.route("/foreman/jobs/add", methods=["GET", "POST"])
@login_required
def foreman_add_job():
    if session.get("role") != "foreman":
        return "Forbidden", 403
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        location = request.form.get("location", "").strip()
    
        if not name:
            flash("Job name is required.")
            return redirect(url_for("foreman_add_job"))

        conn = get_connection()

        job_id = create_job(
            conn,
            name,
            location,
            session["user_id"]
        )

        conn.close()

        flash("Job created.")
        return redirect(url_for("job_detail", job_id=job_id))

    return render_template(
        "add_job.html",
        user=session
    )

@app.route("/jobs/<int:job_id>/assign-machine", methods=["POST"])
@login_required
def assign_machine_to_job_route(job_id):

    if session.get("role") != "foreman":
        return "Forbidden", 403
    
    machine_ids = request.form.getlist("machine_ids")

    if not machine_ids:
        flash("Select at least one machine.")
        return redirect(url_for("job_detail", job_id=job_id))
    
    conn = get_connection()

    try:
        for machine_id in machine_ids:
            assign_machine_to_job(
                conn,
                int(machine_id),
                job_id
            )

            add_job_event(
                conn,
                job_id,
                "machine_assigned"
                f"Machine #{machine_id} was assigned to this job."
            )

        flash("Machines assigned to job.")


    
    finally:
        conn.close()

    return redirect(url_for("job_detail", job_id=job_id))

@app.route("/inspections/<int:inspection_id>")
@login_required
def inspection_detail(inspection_id):

    conn = get_connection()

    inspection = get_inspection_by_id(
        conn,
        inspection_id
    )

    if inspection is None:
        conn.close()
        return "Inspection not found", 404
    
    inspection_items = get_inspection_items(
        conn,
        inspection_id
    )

    conn.close()

    return render_template(
        "inspection_detail.html",
        user=session,
        inspection=inspection,
        inspection_items=inspection_items
    )

@app.route("/jobs/<int:job_id>/remove-machine", methods=["POST"])
@login_required
def remove_machine_from_job_route(job_id):
    if session.get("role") != "foreman":
        return "Forbidden", 403
    
    machine_id = request.form.get("machine_id")

    if not machine_id:
        flash("Missing machine.")
        return redirect(url_for("job_detail", job_id=job_id))
    
    conn = get_connection()

    remove_machine_from_job(
        conn,
        int(machine_id)
    )

    unit_number = get_machine_unit_number(conn, int(machine_id))

    add_job_event(
        conn,
        job_id,
        "machine_removed",
        f"Machine #{unit_number} was removed from this job.",
        session["user_id"]
    )

    conn.close()

    flash("Machine removed from job.")
    return redirect(url_for("job_detail", job_id=job_id))

@app.route("/jobs/<int:job_id>/comments/add", methods=["POST"])
@login_required
def add_job_comment_route(job_id):
    if session.get("role") != "foreman":
        return "Forbidden", 403

    comment = request.form.get("comment", "").strip()

    if not comment:
        flash("Comment cannot be empty.")
        return redirect(url_for("job_detail", job_id=job_id))
    
    conn = get_connection()

    add_job_event(
        conn,
        job_id,
        "foreman_comment",
        comment,
        session["user_id"]
    )

    conn.close()

    flash("comment added.")
    return redirect(url_for("job_detail", job_id=job_id))

@app.route("/work-orders/<int:work_order_id>/parts/add", methods=["POST"])
@login_required
def add_work_order_part_route(work_order_id):

    if session.get("role") not in ["mechanic", "equipment_manager"]:
        return "Forbidden", 403
    
    part_number = request.form.get("part_number", "").strip()
    description = request.form.get("description", "").strip()
    quantity = request.form.get("quantity") or 1
    status = request.form.get("status") or "needed"
    note = request.form.get("note", "").strip()

    if not description:
        flash("Description is required.")
        return redirect(
            url_for(
                "work_order_detail",
                work_order_id=work_order_id
            )
        )
    
    conn = get_connection()

    add_work_order_part(
        conn,
        work_order_id,
        part_number,
        description,
        float(quantity),
        status,
        note
    )

    add_work_order_event(
        conn,
        work_order_id,
        "part_added",
        f"Part added: {description} | Qty: {quantity} | Status: {status}",
        session["user_id"]
    )

    conn.close()

    flash("Part added.")

    return redirect(
        url_for(
            "work_order_detail",
            work_order_id=work_order_id
        )
    )

@app.route("/work-orders/<int:work_order_id>/parts/<int:part_id>/status", methods=["POST"])
@login_required
def update_work_order_part_status_route(work_order_id, part_id):

    if session.get("role") not in ["mechanic", "equipment_manager"]:
        return "Forbidden", 403
    
    status = request.form.get("status")

    if status not in ["needed", "ordered", "received", "installed"]:
        flash("Invalid part status.")
        return redirect(url_for("work_order_detail", work_order_id=work_order_id))
    
    conn = get_connection()

    update_work_order_part_status(
        conn,
        part_id,
        status
    )

    part = get_work_order_part_by_id(conn, part_id)

    part_label = part["part_number"] or part["description"]

    add_work_order_event(
        conn,
        work_order_id,
        "part_status_updated",
        f"Part {part_label} status updated to {status}.",
        session["user_id"]
    )

    conn.close()

    flash("Part status updated.")
    return redirect(url_for("work_order_detail", work_order_id=work_order_id))

@app.route("/manager/parts")
@login_required
def manager_parts():

    if session.get("role") != "equipment_manager":
        return "Forbidden", 403
    
    conn = get_connection()

    parts = get_all_work_order_parts(conn)

    conn.close()

    return render_template(
        "manager_parts.html",
        user=session,
        parts=parts
    )



if __name__ == "__main__":
    #run from /web with python app.py
    app.run(debug=True)