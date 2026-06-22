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

from logic_mods.inspections import (
    get_all_inspections,
    get_inspections_by_user,
    get_open_inspection_for_machine,
    create_open_inspection,
    save_inspection_items,
    close_inspection,
    get_inspection_by_id,
    get_inspection_items
)

from logic_mods.machines import (
    get_machine_by_id,
    get_machine_checklist,
    get_machine_current_meter,
    update_machine_meter,
    update_machine_operational_state
)

from logic_mods.jobs import (
    get_active_jobs
)

inspection_bp = Blueprint("inspection", __name__)


@inspection_bp.route("/machines/<int:machine_id>/inspect", methods=["GET", "POST"])
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
                return redirect(url_for("inspection.new_inspection", machine_id=machine_id))
            
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
                return redirect(url_for("inspection.new_inspection", machine_id=machine_id))
            
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
        return redirect(url_for("machine.machine_profile", machine_id=machine_id))

    conn.close()

    return render_template(
        "inspection_form.html",
        user=session,
        machine=machine,
        checklist_items=checklist_items,
        existing_inspection=existing_inspection,
        jobs=jobs
    )

@inspection_bp.route("/inspections")
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

@inspection_bp.route("/inspections/<int:inspection_id>")
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
