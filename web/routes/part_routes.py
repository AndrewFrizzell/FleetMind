from flask import (
    Blueprint,
    render_template,
    redirect,
    request,
    url_for,
    session,
    flash
)

from fleetmind_db import get_connection
from routes.auth_helpers import login_required

from logic_mods.parts import (
    add_work_order_part,
    get_all_work_order_parts,
    update_work_order_part_status,
    get_work_order_part_by_id,
    get_work_order_parts
)

from logic_mods.work_orders import (
    add_work_order_event
)

part_bp = Blueprint("part", __name__)


@part_bp.route("/work-orders/<int:work_order_id>/parts/add", methods=["POST"])
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
                "work_order.work_order_detail",
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
            "work_order.work_order_detail",
            work_order_id=work_order_id
        )
    )


@part_bp.route("/work-orders/<int:work_order_id>/parts/<int:part_id>/status", methods=["POST"])
@login_required
def update_work_order_part_status_route(work_order_id, part_id):

    if session.get("role") not in ["mechanic", "equipment_manager"]:
        return "Forbidden", 403
    
    status = request.form.get("status")

    if status not in ["needed", "ordered", "received", "installed"]:
        flash("Invalid part status.")
        return redirect(url_for("work_order.work_order_detail", work_order_id=work_order_id))
    
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
    return redirect(url_for("work_order.work_order_detail", work_order_id=work_order_id))


@part_bp.route("/manager/parts")
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
