def get_jobs_for_foreman(conn, foreman_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            job_id,
            name,
            location,
            active
        FROM Job
        WHERE foreman_id = ?
            AND active = 1
        ORDER BY name ASC
    """, (foreman_id,))

    return cur.fetchall()

def get_job_by_id(conn, job_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            j.job_id,
            j.name,
            j.location,
            j.active,
            j.foreman_id,
            u.name AS foreman_name
        FROM Job j
        JOIN User u
            ON j.foreman_id = u.user_id
        WHERE j.job_id = ?
    """, (job_id,))

    return cur.fetchone()

def get_machines_for_job(conn, job_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT
            machine_id,
            unit_number,
            serial_number,
            type,
            make,
            model,
            current_meter_reading,
            operational_state,
            status
        FROM Machine
        WHERE current_job_id = ?
        ORDER BY unit_number ASC
    """, (job_id,))

    return cur.fetchall()

def get_active_jobs(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT job_id, name, location
        FROM Job
        WHERE active = 1
        ORDER BY name ASC
    """)

    return cur.fetchall()

def create_job(conn, name, location, foreman_id):
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO Job (
            name,
            location,
            foreman_id,
            active    
        )
        VALUES (?, ?, ?, 1)
    """, (
        name,
        location,
        foreman_id
    ))

    conn.commit()
    return cur.lastrowid

def get_machines_available_for_job(conn, job_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT
            m.machine_id,
            m.unit_number,
            m.serial_number,
            m.type,
            m.make,
            m.model,
            m.current_meter_reading,
            m.operational_state,
            m.current_job_id,
            j.name AS current_job_name
        FROM Machine m
        LEFT JOIN Job j
            ON m.current_job_id = j.job_id
        WHERE status = 'active'
            AND (
                    current_job_id IS NULL
                    OR current_job_id != ?
                )
        ORDER BY unit_number ASC
    """, (job_id,))

    return cur.fetchall()

def assign_machine_to_job(conn, machine_id, job_id):
    cur = conn.cursor()

    cur.execute("""
        UPDATE Machine
        SET current_job_id = ?
        WHERE machine_id = ?
    """, (job_id, machine_id))

    conn.commit()

def get_open_work_orders_for_job(conn, job_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT
            wo.work_order_id,
            wo.machine_id,
            wo.status,
            wo.priority,
            wo.created_at,
            wo.notes,
            m.unit_number,
            m.make,
            m.model
        FROM WorkOrder wo
        JOIN Machine m
            ON wo.machine_id = m.machine_id
        WHERE m.current_job_id = ?
            AND wo.status != 'closed'
        ORDER BY wo.priority DESC, wo.created_at ASC
    """, (job_id,))

    return cur.fetchall()

def get_recent_inspections_for_job(conn, job_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            i.inspection_id,
            i.machine_id,
            i.inspection_date,
            i.status,
            i.passed,
            i.notes,
                
            m.unit_number,
            m.make,
            m.model,

            u.name AS operator_name
        FROM Inspections i
        JOIN Machine m
            ON i.machine_id = m.machine_id
        JOIN User u
            ON i.operator_id = u.user_id
        WHERE i.job_id = ?
            OR m.current_job_id = ?
        ORDER BY i.inspection_date DESC
        LIMIT 10
    """, (job_id, job_id))

    return cur.fetchall()

def add_job_event(
        conn,
        job_id,
        event_type,
        description,
        user_id=None
):
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO JobEvent (
            job_id,
            user_id,
            event_type,
            description        
        )
        VALUES (?, ?, ?, ?)
    """, (
        job_id,
        user_id,
        event_type,
        description
    ))

    conn.commit()

def get_job_events(conn, job_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT
            je.*,
            u.name AS user_name
        FROM JobEvent je
        LEFT JOIN User u
            ON je.user_id = u.user_id
        WHERE je.job_id = ?
        ORDER BY je.created_at DESC
    """, (job_id,))

    return cur.fetchall()
