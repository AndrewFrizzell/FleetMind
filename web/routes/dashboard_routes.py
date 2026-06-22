from flask import Blueprint, render_template, session

from routes.auth_helpers import login_required

from fleetmind_db import get_connection

from logic_mods.inspections import (
    get_inspections_for_operator
)

from logic_mods.users import (
    get_mechanics
)

from logic_mods.machines import (
    get_all_machines
)

from logic_mods.work_orders import (
    get_open_work_orders,
    get_work_order_status_counts,
    get_work_orders_for_mechanic
)

from logic_mods.jobs import (
    get_jobs_for_foreman
)

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/dashboard", methods=["GET"])
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

        machines = get_all_machines(conn, include_inactive=False)

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
        work_order_counts = get_work_order_status_counts(conn)

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
            machines=machines,
            work_order_counts=work_order_counts
        )
    if role == "mechanic":
        conn = get_connection()
        work_orders = get_work_orders_for_mechanic(
            conn,
            session["user_id"]
        )

        conn.close()

        return render_template(
                    "dashboard_mechanic.html", 
                    user=session,
                    work_orders=work_orders
        )
    
    #fallback
    return "unknown role", 400