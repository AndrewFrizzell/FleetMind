def create_machine_schedule(
        conn,
        machine_id,
        name,
        description,
        interval_type,
        interval_value,
        last_completed_meter=None,
        last_completed_date=None
):
    cur = conn.cursor()

    next_due_meter = None
    next_due_date = None

    if interval_type in ["hours", "miles"] and last_completed_meter is not None:
        next_due_meter = float(last_completed_meter) + float(interval_value)

    cur.execute("""
        INSERT INTO MaintenanceSchedule (
            machine_id,
            name,
            description,
            interval_type,
            interval_value,
            last_completed_meter,
            last_completed_date,
            next_due_meter,
            next_due_date,
            enabled
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        machine_id,
        name,
        description,
        interval_type,
        interval_value,
        last_completed_meter,
        last_completed_date,
        next_due_meter,
        next_due_date,
    ))

    conn.commit()
    return cur.lastrowid

def get_maintenance_schedules_for_machine(conn, machine_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT
            ms.*,
            m.current_meter_reading,
            m.meter_type
        FROM MaintenanceSchedule ms
        JOIN Machine m
            ON ms.machine_id = m.machine_id
        WHERE ms.machine_id = ?
            AND ms.enabled = 1
        ORDER BY ms.name ASC
    """, (
        machine_id,
    ))

    return cur.fetchall()

def get_maintenance_schedule_by_id(conn, maintenance_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            ms.*,
            m.unit_number,
            m.current_meter_reading,
            m.meter_type
        FROM MaintenanceSchedule ms
        JOIN Machine m
            ON ms.machine_id = m.machine_id
        WHERE ms.maintenace_id = ?
    """, (
        maintenance_id,
    ))

    return cur.fetchone()

def get_all_maintenance_schedules(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT
            ms.*,
            m.machine_id,
            m.unit_number,
            m.make,
            m.model,
            m.current_meter_reading,
            m.meter_type,
                
            CASE
                WHEN ms.interval_type IN ('hours', 'miles')
                    AND ms.next_due_meter is NOT NULL
                THEN ms.next_due_meter - m.current_meter_reading
                ELSE NULL
            END AS remaining_meter
        FROM MaintenanceSchedule ms
        JOIN Machine m
            ON ms.machine_id = m.machine_id
        WHERE ms.enabled = 1
        ORDER BY 
            CASE
                WHEN remaining_meter IS NULL THEN 999999
                ELSE remaining_meter
            END ASC
        
    """)

    return cur.fetchall()

def create_maintenance_work_order(conn, maintenance_id, created_by):
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM MaintenanceSchedule
        WHERE maintenance_id = ?
            AND enabled = 1
    """, (maintenance_id,))

    schedule = cur.fetchone()

    if schedule is None:
        raise ValueError("Maintenance schedule not found.")
    
    if schedule["open_work_order_id"]:
        return schedule["open_work_order_id"]
    
    cur.execute("""
        INSERT INTO WorkOrder (
            machine_id,
            created_by,
            status,
            priority,
            notes,
            work_order_type,
            maintenance_id    
        )
        VALUES (?, ?, 'open', 2, ?, 'maintenance', ?)
    """, (
        schedule["machine_id"],
        created_by,
        f"Scheduled maintenance: {schedule['name']}",
        maintenance_id
    ))

    work_order_id = cur.lastrowid

    cur.execute("""
        UPDATE MaintenanceSchedule
        SET open_work_order_id = ?
        WHERE maintenance_id = ?
    """, (work_order_id, maintenance_id))

    conn.commit()
    return work_order_id

def complete_maintenance_schedule(conn, maintenance_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            ms.*,
            m.current_meter_reading
        FROM MaintenanceSchedule ms
        JOIN Machine m
            ON ms.machine_id = m.machine_id
        WHERE ms.maintenance_id = ?
    """, (maintenance_id,))

    schedule = cur.fetchone()

    if schedule is None:
        raise ValueError("Maintenance schedule not found.")
    
    current_meter = schedule["current_meter_reading"]

    next_due_meter = None
    next_due_date = None

    if schedule["interval_type"] in ["hours", "miles"]:
        next_due_meter = float(current_meter) + float(schedule["interval_value"])

    #add date based calculations later

    cur.execute("""
        UPDATE MaintenanceSchedule
        SET last_completed_meter = ?,
            last_completed_date = datetime('now'),
            next_due_meter = ?,
            next_due_date = ?,
            open_work_order_id = null
        WHERE maintenance_id = ?
    """, (
        current_meter,
        next_due_meter,
        next_due_date,
        maintenance_id
    ))

    conn.commit()