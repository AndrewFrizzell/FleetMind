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
    update_work_order_part_details,
    link_catalog_part_to_request
)

from logic_mods.work_orders import (
    add_work_order_event,
    update_work_order_status
)

from logic_mods.part_catalog import (
    get_all_parts,
    search_parts,
    get_part_by_id,
    create_part
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
    
    catalog_parts = get_all_parts(conn)
    
    linked_part = None

    if part["part_id"]:
        linked_part = get_part_by_id(
            conn,
            part["part_id"]
        )

    
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
        part=part,
        catalog_parts=catalog_parts,
        linked_part=linked_part
    )

@part_bp.route("/manager/parts/add", methods=["GET", "POST"])
@login_required
def add_catalog_part():

    if session.get("role") != "equipment_manager":
        return "Forbidden", 403
    
    work_order_part_id = request.args.get(
        "work_order_part_id",
        type=int
    )

    
    if request.method == "POST":
        work_order_part_id = request.form.get("work_order_part_id", type=int)
        part_number = (request.form.get("part_number") or "").strip()
        name = (request.form.get("name") or "").strip()
        description = (request.form.get("description") or "").strip()
        manufacturer = (request.form.get("manufacturer") or "").strip()
        unit_of_measure = (request.form.get("unit_of_measure") or "each").strip()
        default_cost = request.form.get("default_cost") or None

        if not name:
            flash("Part name is required.")
            return redirect(url_for("part.add_catalog_part", work_order_part_id=work_order_part_id))
        
        conn = get_connection()

        try:
            create_part(
                conn,
                part_number=part_number,
                name=name,
                description=description,
                manufacturer=manufacturer,
                unit_of_measure=unit_of_measure,
                default_cost=float(default_cost) if default_cost else None
            )
        
            flash("catalog part added.")
            if work_order_part_id:
                return redirect( url_for(
                    "part.manager_part_request",
                    work_order_part_id=work_order_part_id
                ))
            
            return redirect(url_for("part.manager_parts"))
        
        except Exception as e:
            conn.rollback()
            flash(f"Error adding catalog part: {e}")
            return redirect(url_for("part.add_catalog_part", work_order_part_id=work_order_part_id))
        
        finally:
            conn.close()

    return render_template(
        "add_catalog_part.html",
        user=session,
        work_order_part_id=work_order_part_id
    )

@part_bp.route(
    "/part-request/<int:work_order_part_id>/link-catalog", methods=["POST"]
)
@login_required
def link_catalog_part_route(work_order_part_id):

    if session.get("role") != "equipment_manager":
        return "Forbidden", 403
    
    catalog_part_id = request.form.get("catalog_part_id")

    if not catalog_part_id:
        flash("Select a catalog part.")
        return redirect(
            url_for(
                "part.manage_part_request",
                work_order_part_id=work_order_part_id
            )
        )
    
    conn = get_connection()

    try:
        part_request = get_work_order_part_by_id(
            conn,
            work_order_part_id
        )
        if part_request is None:
            return "Part request not found", 404
        
        link_catalog_part_to_request(
            conn,
            work_order_part_id,
            int(catalog_part_id)
        )

        linked_part = get_part_by_id(
            conn,
            int(catalog_part_id)
        )

        add_work_order_event(
            conn,
            part_request["work_order_id"],
            "catalog_part_linked",
            (
                f"Part request linked to catalog part: "
                f"{linked_part['part_number'] or 'No part number'} "
                f"-{linked_part['name']}"
            ),
            session["user_id"]
        )

        flash("Catalog part linked.")

    except Exception as e:
        conn.rollback()
        print("LINK CATALOG PART ERROR:", e)
        flash(f"Error linking catalog part: {e}")

    finally:
        conn.close()

    return redirect(
        url_for(
            "part.manage_part_request",
            work_order_part_id=work_order_part_id
        )
    )
