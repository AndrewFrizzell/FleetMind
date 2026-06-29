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

