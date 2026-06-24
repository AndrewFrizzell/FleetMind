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

from routes.work_order_routes import (
    work_order_bp
)

from routes.part_routes import (
    part_bp
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
app.register_blueprint(work_order_bp)
app.register_blueprint(part_bp)


if __name__ == "__main__":
    #run from /web with python app.py
    app.run(debug=True)