import os
import sys
# Add project root (fleetmind/) to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, render_template, request, redirect, url_for, session, flash

from fleetmind_db import get_connection

from routes.auth_helpers import (
    login_required
)

from routes.auth_routes import (
    auth_bp
)

from routes.dashboard_routes import (
    dashboard_bp
)

from routes.machine_routes import (
    machine_bp
)

from routes.inspection_routes import (
    inspection_bp
)

from routes.job_routes import (
    job_bp
)

from logic_mods.users import (
    get_mechanics,
    get_user_by_id
)

from logic_mods.parts import (
    add_work_order_part,
    get_all_work_order_parts,
    update_work_order_part_status,
    get_work_order_part_by_id,
    get_work_order_parts
)

from logic_mods.jobs import (
    get_jobs_for_foreman,
    get_job_by_id,
    get_machines_for_job,
    get_active_jobs,
    create_job,
    get_machines_available_for_job,
    assign_machine_to_job,
    get_open_work_orders_for_job,
    get_recent_inspections_for_job,
    add_job_event,
    get_job_events
)

from logic_mods.machines import(
    create_machine,
    update_machine_meter,
    get_machine_current_meter,
    get_all_machines,
    get_machine_by_id,
    get_open_work_orders_for_machine,
    get_recent_inspections_for_machine,
    get_open_faults_for_machine,
    remove_machine_from_job,
    get_machine_unit_number,
    update_machine_operational_state,
    refresh_machine_operational_state,
    get_master_checklist_items,
    create_master_checklist_item,
    get_machine_checklist,
    add_item_to_machine_checklist,
    remove_item_from_machine_checklist,
    get_active_checklist_items
)

from logic_mods.inspections import(
    get_all_inspections,
    get_inspections_by_user,
    get_open_inspection_for_machine,
    create_open_inspection,
    save_inspection_items,
    close_inspection,
    get_inspections_for_operator,
    get_operator_machine_list,
    get_inspection_by_id,
    get_inspection_items
)

from logic_mods.work_orders import (
    get_open_work_orders,
    get_all_work_orders,
    get_work_order_by_id,
    add_work_order_comment,
    add_work_order_event,
    get_work_order_timeline,
    update_work_order_status,
    close_machine_fault_for_work_order,
    get_work_order_status_counts,
    assign_work_order_mechanic,
    get_work_orders_for_mechanic,
)



app = Flask(__name__)
app.secret_key = "dev-secret-change-me" #change this later

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(machine_bp)
app.register_blueprint(inspection_bp)
app.register_blueprint(job_bp)










@app.route("/work-orders/<int:work_order_id>")
@login_required
def work_order_detail(work_order_id):
    conn = get_connection()

    work_order = get_work_order_by_id(conn, work_order_id)
    timeline = get_work_order_timeline(conn, work_order_id)
    parts = get_work_order_parts(conn, work_order_id)
    mechanics = get_mechanics(conn)

    conn.close()

    if work_order is None:
        return "Work order not found", 404
    
    return render_template(
        "work_order_detail.html",
        user=session,
        work_order=work_order,
        timeline=timeline,
        parts=parts,
        mechanics=mechanics
    )

@app.route("/work-orders/<int:work_order_id>/assign-mechanic", methods=["POST"])
@login_required
def assign_work_order_mechanic_route(work_order_id):


    if session.get("role") != "equipment_manager":
        return "Forbidden", 403
    
    mechanic_id = request.form.get("mechanic_id")

    if not mechanic_id:
        flash("Please select a mechanic.")
        return redirect(
            url_for("work_order_detail", work_order_id=work_order_id)
        )
    
    conn = get_connection()

    try:
        assign_work_order_mechanic(
            conn,
            work_order_id,
            int(mechanic_id)
        )


        mechanic = get_user_by_id(
            conn,
            int(mechanic_id)
        )
        

        add_work_order_event(
            conn,
            work_order_id,
            "mechanic_assigned",
            f"Assigned to mechanic: {mechanic['name']}",
            session["user_id"],
        )


        flash("Mechanic assigned.")

    except Exception as e:
        conn.rollback()
        flash(f"Error assigning mechanic: {e}")

    finally:
        conn.close()

    return redirect(
        url_for(
            "work_order_detail",
            work_order_id=work_order_id
        )
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














@app.route("/manager/work-orders")
@login_required
def manager_work_orders():

    if session.get("role") != "equipment_manager":
        flash("you do not have permission to view that page.")
        return redirect(url_for("dashboard"))
    
    conn= get_connection()

    try:
        work_orders = get_all_work_orders(conn)

        status_order = [
            "repair_complete",
            "waiting_on_parts",
            "in_progress",
            "assigned",
            "open",
            "closed"
        ]

        status_labels = {
            "repair_complete": "Repair Complete",
            "waiting_on_parts": "Waiting On Parts",
            "in_progress": "In Progress",
            "assigned": "Assigned",
            "open": "Open",
            "closed": "Closed"
        }

        grouped_work_orders = {
            status: [] for status in status_order
        }

        for wo in work_orders:
            grouped_work_orders[wo["status"]].append(wo)

        return render_template(
            "work_orders.html",
            work_orders=work_orders,
            grouped_work_orders=grouped_work_orders,
            status_order=status_order,
            status_labels=status_labels,
            role=session.get("role")
        )
    
    finally:
        conn.close()











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

@app.route("/work-orders/<int:work_order_id>/status", methods=["POST"])
@login_required
def update_work_order_status_route(work_order_id):

    if session.get("role") not in ["mechanic", "equipment_manager"]:
        return "Forbidden", 403
    
    new_status = request.form.get("status")

    conn = get_connection()

    try:
        update_work_order_status(
            conn,
            work_order_id,
            new_status
        )

        add_work_order_event(
            conn,
            work_order_id,
            "status_updated",
            f"Work order status changed to {new_status}.",
            session["user_id"]
        )

        if new_status == "repair_complete":
            cur = conn.cursor()
            
            cur.execute("""
                SELECT machine_id
                FROM WorkOrder
                WHERE work_order_id = ?
             """, (work_order_id,))
            
            row = cur.fetchone()

            if row:
                machine_id = row["machine_id"]
                
                close_machine_fault_for_work_order(
                    conn,
                    work_order_id
                )

                refresh_machine_operational_state(
                    conn,
                    machine_id
                )

                add_work_order_event(
                    conn,
                    work_order_id,
                    "repair_complete",
                    "Repair marked complete. Linked fault closed and machine status refreshed.",
                    session["user_id"]
                )

        flash("Work order status updated.")

    except Exception as e:
        conn.rollback()
        flash(f"Error updating work order status: {e}")

    finally:
        conn.close()

    return redirect(
        url_for(
            "work_order_detail",
            work_order_id=work_order_id
        )
    )



if __name__ == "__main__":
    #run from /web with python app.py
    app.run(debug=True)