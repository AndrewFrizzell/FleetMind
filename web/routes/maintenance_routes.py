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
    get_all_maintenance_schedules
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