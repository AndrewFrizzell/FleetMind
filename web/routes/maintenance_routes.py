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

from logic_mods.maintenance import (
    get_all_maintenance_schedules,
    create_maintenance_work_order
)

maintenance_bp = Blueprint("maintenance", __name__)

@maintenance_bp.route("/manager/maintenance")
@login_required
def manager_maintenance():

    if session.get("role") != "equipment_manager":
        return "Forbidden", 403
    
    conn = get_connection()
    schedules = get_all_maintenance_schedules(conn)
    conn.close()

    return render_template(
        "manager_maintenance.html",
        user=session,
        schedules=schedules
    )

@maintenance_bp.route("/maintenance/<int:maintenance_id>/create-work-order", methods=["POST"])
@login_required
def create_maintenance_work_order_route(maintenance_id):

    if session.get("role") != "equipment_manager":
        return "Forbidden", 403
    
    conn = get_connection()

    try:
        work_order_id = create_maintenance_work_order(
            conn,
            maintenance_id,
            session["user_id"]
        )
    
    except Exception as e:
        conn.rollback()
        print("CREATE MAINT WO ERROR:", e)
        flash(f"Error creating maintenance work order: {e}")

    finally:
        conn.close()

    return redirect(url_for("maintenance.manager_maintenance"))