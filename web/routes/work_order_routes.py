from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from fleetmind_db import get_connection
from routes.auth_helpers import login_required

from logic_mods.work_orders import (
    get_all_work_orders,
    get_work_order_by_id,
    add_work_order_comment,
    add_work_order_event,
    get_work_order_timeline,
    update_work_order_status,
    close_machine_fault_for_work_order,
    assign_work_order_mechanic,
    
)

from logic_mods.machines import (
    refresh_machine_operational_state
)

from logic_mods.parts import (
    get_work_order_parts,
)

from logic_mods.users import (
    get_mechanics,
    get_user_by_id
)

from logic_mods.maintenance import (
    complete_maintenance_schedule
)

work_order_bp = Blueprint("work_order", __name__)

@work_order_bp.route("/work-orders/<int:work_order_id>")
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


@work_order_bp.route("/work-orders/<int:work_order_id>/assign-mechanic", methods=["POST"])
@login_required
def assign_work_order_mechanic_route(work_order_id):


    if session.get("role") != "equipment_manager":
        return "Forbidden", 403
    
    mechanic_id = request.form.get("mechanic_id")

    if not mechanic_id:
        flash("Please select a mechanic.")
        return redirect(
            url_for("work_order.work_order_detail", work_order_id=work_order_id)
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
            "work_order.work_order_detail",
            work_order_id=work_order_id
        )
    )


@work_order_bp.route("/work-orders/<int:work_order_id>/comments/add", methods=["POST"])
@login_required
def add_work_order_comment_route(work_order_id):
    comment = request.form.get("comment", "").strip()

    if not comment:
        flash("Comment cannot be empty.")
        return redirect(url_for("work_order.work_order_detail", work_order_id=work_order_id))
    
    conn = get_connection()

    add_work_order_comment(
        conn,
        work_order_id,
        session["user_id"],
        comment
    )

    conn.close()
    flash("Comment added.")
    return redirect(url_for("work_order.work_order_detail", work_order_id=work_order_id))


@work_order_bp.route("/manager/work-orders")
@login_required
def manager_work_orders():

    if session.get("role") != "equipment_manager":
        flash("you do not have permission to view that page.")
        return redirect(url_for("dashboard.dashboard"))
    
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


@work_order_bp.route("/work-orders/<int:work_order_id>/status", methods=["POST"])
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
                SELECT 
                    machine_id,
                    work_order_type,
                    maintenance_id
                FROM WorkOrder
                WHERE work_order_id = ?
             """, (work_order_id,))
            
            row = cur.fetchone()

            if row:
                machine_id = row["machine_id"]

                if row["work_order_type"] == "repair":
                
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
                
                elif row["work_order_type"] == "maintenance" and row["maintenance_id"]:

                    complete_maintenance_schedule(
                        conn,
                        row["maintenance_id"]
                    )

                    add_work_order_event(
                        conn,
                        work_order_id,
                        "maintenance_complete",
                        "maintenance marked complete. Maintenance schedule was reset.",
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
            "work_order.work_order_detail",
            work_order_id=work_order_id
        )
    )