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
    get_open_part_requests,
    update_work_order_part_details
)

from logic_mods.work_orders import (
    add_work_order_event,
    update_work_order_status
)

from logic_mods.part_catalog import (
    get_all_parts,
    search_parts,
    get_all_parts_by_id,
)

part_bp = Blueprint("part", __name__)


@part_bp.route("/work-orders/<int:work_order_id>/parts/add", methods=["POST"])
@login_required
def add_work_order_part_route(work_order_id):

    print("ADD PART ROUTE HIT")
    print("WORK ORDER ID:", work_order_id)
    print("FORM:", request.form)

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

    try:
        add_work_order_part(
            conn,
            work_order_id,
            part_number,
            description,
            float(quantity),
            status,
            note,
            part_id=None
        )

        update_work_order_status(
            conn,
            work_order_id,
            "waiting_on_parts"
        )

        add_work_order_event(
            conn,
            work_order_id,
            "part_added",
            f"Part requested: {description} | Qty: {quantity} | Status: {status}",
            session["user_id"]
        )

        flash("Part request added. Work order moved to Waiting on Parts.")

    except Exception as e:
        conn.rollback()
        print("ADD PART ERROR:", e)
        flash(f"Error adding part: {e}")

    finally:
        conn.close()


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

    parts = get_all_parts(conn)

    conn.close()

    return render_template(
        "manager_parts.html",
        user=session,
        parts=parts
    )

@part_bp.route("/manager/part-requests")
@login_required
def manager_part_request():
    
    if session.get("role") != "equipment_manager":
        return "Forbidden", 403
    
    conn = get_connection()
    part_request = get_open_part_requests(conn)
    conn.close()

    return render_template(
        "manager_part_requests.html",
        user=session,
        part_request=part_request
    )

@part_bp.route("/part-requests/<int:work_order_part_id>", methods=["GET", "POST"])
@login_required
def manage_part_request(work_order_part_id):

    if session.get("role") != "equipment_manager":
        return "Forbidden", 403
    
    conn = get_connection()
    part = get_work_order_part_by_id(conn, work_order_part_id)

    if part is None:
        conn.close()
        return "Part request not found.", 404
    
    if request.method == "POST":
        part_number = (request.form.get("part_number") or "").strip()
        description = (request.form.get("description") or "").strip()
        quantity = request.form.get("quantity") or 1
        status = request.form.get("status") or "needed"
        note = (request.form.get("note") or "").strip()

        if not description:
            conn.close()
            flash("Description is required.")
            return redirect(url_for("part.manage_part_request", work_order_part_id=work_order_part_id))
        
        update_work_order_part_details(
            conn,
            work_order_part_id,
            part_number,
            description,
            float(quantity),
            status,
            note
        )

        add_work_order_event(
            conn,
            part["work_order_id"],
            "part_request_updated",
            f"Part request updated: {description} | status: {status}",
            session["user_id"]
        )

        flash("Part request update.")
        conn.close()

        return redirect(url_for("work_order.work_order_detail", work_order_id=part["work_order_id"]))
    
    conn.close()

    return render_template(
        "manage_part_request.html",
        user=session,
        part=part
    )