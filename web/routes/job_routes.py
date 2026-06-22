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

from logic_mods.jobs import (
    get_job_by_id,
    get_machines_for_job,
    assign_machine_to_job,
    create_job,
    get_machines_available_for_job,
    get_open_work_orders_for_job,
    get_recent_inspections_for_job,
    get_job_events,
    add_job_event
)

from logic_mods.machines import (
    remove_machine_from_job,
    get_machine_unit_number
)

job_bp = Blueprint("job", __name__)

@job_bp.route("/jobs/<int:job_id>")
@login_required
def job_detail(job_id):

    conn = get_connection()

    job = get_job_by_id(conn, job_id)

    if job is None:
        conn.close()
        return "Job not found", 404
    
    open_work_orders = get_open_work_orders_for_job(conn, job_id)
    recent_inspections = get_recent_inspections_for_job(conn, job_id)
    job_events = get_job_events(conn, job_id)
    machines = get_machines_for_job(conn, job_id)
    unassigned_machines = get_machines_available_for_job(conn, job_id)

    conn.close()

    return render_template (
        "job_detail.html",
        user=session,
        job=job,
        machines=machines,
        unassigned_machines=unassigned_machines,
        open_work_orders=open_work_orders,
        recent_inspections=recent_inspections,
        job_events=job_events
    )


@job_bp.route("/foreman/jobs/add", methods=["GET", "POST"])
@login_required
def foreman_add_job():
    if session.get("role") != "foreman":
        return "Forbidden", 403
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        location = request.form.get("location", "").strip()
    
        if not name:
            flash("Job name is required.")
            return redirect(url_for("job.foreman_add_job"))

        conn = get_connection()

        job_id = create_job(
            conn,
            name,
            location,
            session["user_id"]
        )

        conn.close()

        flash("Job created.")
        return redirect(url_for("job.job_detail", job_id=job_id))

    return render_template(
        "add_job.html",
        user=session
    )


@job_bp.route("/jobs/<int:job_id>/assign-machine", methods=["POST"])
@login_required
def assign_machine_to_job_route(job_id):

    if session.get("role") != "foreman":
        return "Forbidden", 403
    
    machine_ids = request.form.getlist("machine_ids")
    
    if not machine_ids:
        flash("Select at least one machine.")
        return redirect(url_for("job.job_detail", job_id=job_id))
    
    conn = get_connection()

    try:
        for machine_id in machine_ids:
            unit_number =  get_machine_unit_number(conn, int(machine_id))


            assign_machine_to_job(
                conn,
                int(machine_id),
                job_id
            )

            add_job_event(
                conn,
                job_id,
                "machine_assigned",
                f"Machine #{unit_number} was assigned to this job.",
                session["user_id"]
            )

        flash("Machines assigned to job.")


    
    finally:
        conn.close()

    return redirect(url_for("job.job_detail", job_id=job_id))


@job_bp.route("/jobs/<int:job_id>/remove-machine", methods=["POST"])
@login_required
def remove_machine_from_job_route(job_id):
    if session.get("role") != "foreman":
        return "Forbidden", 403
    
    machine_id = request.form.get("machine_id")

    if not machine_id:
        flash("Missing machine.")
        return redirect(url_for("job.job_detail", job_id=job_id))
    
    conn = get_connection()

    remove_machine_from_job(
        conn,
        int(machine_id)
    )

    unit_number = get_machine_unit_number(conn, int(machine_id))

    add_job_event(
        conn,
        job_id,
        "machine_removed",
        f"Machine #{unit_number} was removed from this job.",
        session["user_id"]
    )

    conn.close()

    flash("Machine removed from job.")
    return redirect(url_for("job.job_detail", job_id=job_id))


@job_bp.route("/jobs/<int:job_id>/comments/add", methods=["POST"])
@login_required
def add_job_comment_route(job_id):
    if session.get("role") != "foreman":
        return "Forbidden", 403

    comment = request.form.get("comment", "").strip()

    if not comment:
        flash("Comment cannot be empty.")
        return redirect(url_for("job.job_detail", job_id=job_id))
    
    conn = get_connection()

    add_job_event(
        conn,
        job_id,
        "foreman_comment",
        comment,
        session["user_id"]
    )

    conn.close()

    flash("comment added.")
    return redirect(url_for("job.job_detail", job_id=job_id))