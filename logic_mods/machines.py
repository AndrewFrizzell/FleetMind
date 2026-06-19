#add machine
def create_machine(conn,
                    unit_number,
                    department,
                    serial_number, 
                    vin_number,
                    machine_type, 
                    make="", 
                    model="", 
                    year=None,
                    meter_type="hours",
                    current_meter_reading=0, 
                    status="active", 
                    current_job_id=None,
                    photo_url=None
                    ):
    cur = conn.cursor()

    unit_number = (unit_number or "").strip().upper()
    serial_number = (serial_number or "").strip().upper()
    machine_type = (machine_type or "").strip().upper()
    make = (make or "").strip().upper()
    model = (model or "").strip().upper()


    cur.execute("""
        INSERT INTO Machine (
            unit_number,
            department,
            serial_number,
            vin_number,
            type,
            make,
            model,
            year,
            meter_type,
            current_meter_reading,
            status,
            photo_url,
            current_job_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        unit_number,
        department,
        serial_number,
        vin_number,
        machine_type,
        make,
        model,
        year,
        meter_type,
        current_meter_reading,
        status,
        photo_url,
        current_job_id
    ))

    conn.commit()
    return cur.lastrowid


def update_machine_meter(conn, machine_id, new_meter_reading):
    cur = conn.cursor()

    cur.execute("""
        UPDATE Machine
        SET current_meter_reading = ?
        WHERE machine_id = ?
    """, (new_meter_reading, machine_id))

    conn.commit()


def get_machine_current_meter(conn, machine_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT current_meter_reading
        FROM Machine
        WHERE machine_id = ?
    """, (machine_id,))

    return cur.fetchone()


#get machine list 
def get_all_machines(conn, include_inactive=True):
    cur = conn.cursor()
    
    if include_inactive:
        cur.execute("""
            SELECT
                m.machine_id,
                m.unit_number,
                m.department,
                m.serial_number,
                m.vin_number,
                m.type,
                m.make,
                m.model,
                m.year,
                m.meter_type,
                m.current_meter_reading,
                m.status,
                m.operational_state,
                m.photo_url,
                m.current_job_id,
                j.name AS job_name
            FROM Machine m
            LEFT JOIN Job j ON m.current_job_id = j.job_id
            ORDER BY m.serial_number ASC
        """)
    else:
        cur.execute("""
            SELECT
                m.machine_id,
                m.unit_number,
                m.department,
                m.serial_number,
                m.type,
                m.make,
                m.model,
                m.year,
                m.meter_type,
                m.current_meter_reading,
                m.status,
                m.operational_state,
                m.photo_url,
                m.current_job_id,
                j.name
            FROM Machine m
            LEFT JOIN Job j ON m.current_job_id = j.job_id
            WHERE m.status = 'active'
            ORDER BY m.serial_number ASC
        """)

    return cur.fetchall()

def get_machine_by_id(conn, machine_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT
            m.machine_id,
            m.vin_number,
            m.unit_number,
            m.serial_number,
            m.type,
            m.make,
            m.model,
            m.year,
            m.status,
            m.operational_state,
            m.current_meter_reading,
            m.current_job_id,
            j.name AS job_name,
            j.location AS job_location
        FROM Machine m
        LEFT JOIN Job j ON m.current_job_id = j.job_id
        WHERE m.machine_id = ?
    """, (machine_id,))
    return cur.fetchone()

def get_open_work_orders_for_machine(conn, machine_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT
            wo.work_order_id,
            wo.status,
            wo.priority,
            wo.created_at,
            wo.completed_at,
            wo.notes,
            u.name AS assigned_to_name
        FROM WorkOrder wo
        LEFT JOIN User u
            ON wo.assigned_to = u.user_id
        WHERE wo.machine_id = ?
            AND wo.status != 'closed'
        ORDER BY wo.priority DESC, wo.created_at ASC
    """, (machine_id,))

    return cur.fetchall()

def get_recent_inspections_for_machine(conn, machine_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            i.inspection_id,
            i.inspection_date,
            i.passed,
            i.notes,
            u.name AS operator_name
        FROM Inspections i 
        JOIN User u ON i.operator_id = u.user_id
        WHERE i.machine_id = ?
        ORDER BY i.inspection_date DESC
        LIMIT 10
    """, (machine_id,))
    return cur.fetchall()

def get_open_faults_for_machine(conn, machine_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            fault_id,
            item_name,
            first_reported_at,
            work_order_id
        FROM MachineFault
        WHERE machine_id = ?
            AND status = 'open'
        ORDER BY first_reported_at DESC
    """,(machine_id,))

    return cur.fetchall()

def remove_machine_from_job(conn, machine_id):
    cur = conn.cursor()

    cur.execute("""
        UPDATE Machine
        SET current_job_id = NULL
        WHERE machine_id = ?
    """, (machine_id,))

    conn.commit()


def get_machine_unit_number(conn, machine_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT unit_number
        FROM Machine
        WHERE machine_id = ?
    """, (machine_id,))

    row = cur.fetchone()

    if row is None:
        return f"Machine #{machine_id}"
    
    return row["unit_number"]

def update_machine_operational_state(conn, machine_id, operational_state):
    cur = conn.cursor()

    cur.execute("""
        UPDATE Machine
        SET operational_state = ?
        WHERE machine_id = ?
    """, (operational_state, machine_id))

    conn.commit()

def refresh_machine_operational_state(conn, machine_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT operator_decision
        FROM MachineFault
        WHERE machine_id = ?
            AND status = 'open'
    """, (machine_id,))

    open_faults = cur.fetchall()

    if not open_faults:
        new_state = "running"
    elif any(fault["operator_decision"] == "down" for fault in open_faults):
        new_state = 'down'
    else: 
        new_state = "running_with_faults"

    cur.execute("""
        UPDATE Machine
        SET operational_state = ?
        WHERE machine_id = ?
    """, (new_state, machine_id))

    conn.commit()

def get_master_checklist_items(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT item_id, name, description, active
        FROM MasterChecklistItem
        WHERE active = 1
        ORDER BY name ASC
    """)
    return cur.fetchall()


def create_master_checklist_item(conn, name, description=None):
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO MasterChecklistItem(name, description)
        VALUES (?, ?)
    """,(name, description))

    conn.commit()

    cur.execute("""
        SELECT item_id
        FROM MasterChecklistItem
        WHERE name = ?
    """, (name,))

    return cur.fetchone()

def get_machine_checklist(conn, machine_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT
            mci.machine_checklist_item_id,
            mci.machine_id,
            mci.master_item_id,
            mci.required,
            mci.active,
            mci_item.name,
            mci_item.description
        FROM MachineChecklistItem mci
        JOIN MasterChecklistItem mci_item
            ON mci.master_item_id = mci_item.item_id
        WHERE mci.machine_id = ?
            AND mci.active = 1
        ORDER BY mci_item.name ASC
    """, (machine_id,))
    return cur.fetchall()

def add_item_to_machine_checklist(conn, machine_id, master_item_id):
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO MachineChecklistItem (
            machine_id,
            master_item_id,
            required,
            active        
        )
        VALUES (?, ?, 1, 1)
    """, (machine_id, master_item_id))

    cur.execute("""
        UPDATE MachineChecklistItem
        SET active = 1
        WHERE machine_id = ?
            AND master_item_id = ?
    """, (machine_id, master_item_id))
    conn.commit()

def remove_item_from_machine_checklist(conn, machine_checklist_item_id):
    cur = conn.cursor()
    cur.execute("""
        UPDATE MachineChecklistItem
        SET active = 0
        WHERE machine_checklist_item_id = ?
    """, (machine_checklist_item_id,))
    conn.commit()

