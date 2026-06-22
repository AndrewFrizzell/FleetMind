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

from logic_mods.machines import (
    get_all_machines,
    get_machine_by_id,
    get_open_faults_for_machine,
    get_open_work_orders_for_machine,
    get_recent_inspections_for_machine,
    get_machine_checklist,
    get_master_checklist_items,
    add_item_to_machine_checklist,
    remove_item_from_machine_checklist,
    create_machine,
    create_master_checklist_item
)

machine_bp = Blueprint("machine", __name__)


@machine_bp.route("/machines")
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




@machine_bp.route("/machines/<int:machine_id>")
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


@machine_bp.route("/manager/machines/add", methods=["GET", "POST"])
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
            return redirect(url_for("machine.machine_profile", machine_id=machine_id))
        
        except Exception as e:
            conn.rollback()
            flash(f"Error adding machine: {e}")
            return redirect(url_for("machine.add_machine"))
        
        finally:
            conn.close()
        
    return render_template("add_machine.html", user=session)

@machine_bp.route("/manager/machines/<int:machine_id>/checklist", methods=["GET"])
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


@machine_bp.route("/manager/machines/<int:machine_id>/checklist/add", methods=["POST"])
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


    return redirect(url_for("machine.manage_machine_checklist", machine_id=machine_id))

@machine_bp.route("/manager/machine-checklist/remove", methods=["POST"])
@login_required
def remove_machine_checklist_item():
    if session.get("role") != "equipment_manager":
        return "Forbidden", 403
    
    machine_checklist_item_id = request.form.get("machine_checklist_item_id")
    machine_id = request.form.get("machine_id")

    conn = get_connection()
    remove_item_from_machine_checklist(conn, int(machine_checklist_item_id))
    conn.close()

    return redirect(url_for("machine.manage_machine_checklist", machine_id=int(machine_id)))