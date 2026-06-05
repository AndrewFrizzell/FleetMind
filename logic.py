#=====================================
#inspections
#=====================================

#get all inspections
def get_all_inspections(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT
            i.inspection_id,
            i.machine_id,
            i.inspection_date,
            i.passed,
            i.notes,
            u.name AS operator_name,
            m.serial_number,
            m.type,
            m.make,
            m.model
        FROM Inspections i 
        JOIN User u
            ON i.operator_id = u.user_id
        JOIN Machine m
            ON i.machine_id = m.machine_id
        ORDER BY i.inspection_date DESC
    """)

    return cur.fetchall()

def get_inspections_by_user(conn, user_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            i.inspection_id,
            i.machine_id,
            i.inspection_date,
            i.passed,
            i.notes,
            m.serial_number,
            m.type,
            m.make,
            m.model
        FROM Inspections i
        JOIN Machine m
            ON i.machine_id = m.machine_id
        WHERE i.operator_id = ?
        ORDER BY i.inspection_date DESC
    """, (user_id,))

    return cur.fetchall()


def get_active_checklist_items(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT item_id, name, description
        FROM MasterChecklistItem
        WHERE active = 1
        ORDER BY item_id ASC
    """)
    return cur.fetchall()

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

def get_open_inspection_for_machine(conn, machine_id):
    cur=conn.cursor()
    cur.execute("""
        SELECT *
        FROM Inspections
        WHERE machine_id = ?
            AND status = 'open'
        ORDER BY inspection_date DESC
        LIMIT 1
    """, (machine_id,))

    return cur.fetchone()

def create_open_inspection(conn, machine_id, operator_id, opening_meter=None, notes=None):
    existing_inspection = get_open_inspection_for_machine(conn, machine_id)

    if existing_inspection:
        return existing_inspection
    
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO Inspections (
            machine_id,
            operator_id,
            opening_meter,
            notes,
            status,
            passed    
            )
        VALUES (?, ?, ?, ?, 'open', 1)
    """,(machine_id, operator_id, opening_meter, notes))

    conn.commit()

    inspection_id = cur.lastrowid

    cur.execute("""
        SELECT *
        FROM Inspections
        WHERE inspection_id = ?
    """, (inspection_id,))

    return cur.fetchone()

def close_inspection(conn, inspection_id, closing_meter=None):
    cur = conn.cursor()
    cur.execute("""
        UPDATE Inspections
        SET status = 'closed',
            closing_meter = ?,
            closed_at = datetime('now')
        WHERE inspection_id = ?
    """, (closing_meter, inspection_id))

    conn.commit()

def save_inspection_items(conn, inspection_id, machine_id, operator_id, results):
    cur = conn.cursor()

    cur.execute("""
    DELETE FROM InspectionItems
    WHERE inspection_id = ?
    """, (inspection_id,))

    for item_name, passed in results.items():
        cur.execute("""
            INSERT INTO InspectionItems (
                inspection_id,
                item_name,
                passed,
                note
            )
            VALUES (?, ?, ?, ?)
        """, (inspection_id,
              item_name,
              int(passed),
              ""
            ))
        if not passed:
            existing_fault = get_open_machine_fault(
                conn,
                machine_id,
                item_name
            )
            if existing_fault:
                update_machine_fault_last_reported(
                    conn,
                    existing_fault["fault_id"]
                )
            else:
                fault_id = create_machine_fault(
                    conn,
                    machine_id,
                    item_name
                )
                cur.execute("""
                    INSERT INTO WorkOrder (
                        machine_id,
                        created_by,
                        status,
                        priority,
                        notes        
                    )
                    VALUES (?, ?, 'open', 2, ?)
                """, (
                    machine_id,
                    operator_id,
                    f"Auto-created from inspection: {item_name}"
                ))

                work_order_id = cur.lastrowid

                add_work_order_event(
                    conn,
                    work_order_id,
                    "work_order_created",
                    f"Work order #{work_order_id} created from failed inspection item: {item_name}",
                    operator_id
                )

                link_fault_to_work_order(
                    conn,
                    fault_id,
                    work_order_id
                )

    
    cur.execute("""
        UPDATE Inspections
        SET passed = ?
        WHERE inspection_id = ?
    """, (
        int(all(results.values())),
        inspection_id
    ))
        
    conn.commit()

def get_inspections_for_operator(conn, operator_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            i.inspection_id,
            i.machine_id,
            i.inspection_date,
            i.status,
            i.opening_meter,
            i.closing_meter,
            i.closed_at,
            i.passed,
            i.notes,
                
            m.unit_number,
            m.serial_number,
            m.type,
            m.make,
            m.model,
            m.current_meter_reading
                
        FROM Inspections i 
        JOIN Machine m
            ON i.machine_id = m.machine_id
        WHERE i.operator_id = ?
        ORDER BY i.inspection_date DESC
    """,(operator_id,))

    return cur.fetchall()

def get_operator_machine_list(conn):
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
                
            i.inspection_id AS open_inspection_id,
            i.operator_id AS open_operator_id,
            u.name AS open_operator_name
            
        FROM Machine m
        
        LEFT JOIN Inspections i 
            ON m.machine_id = i.machine_id
            AND i.status = 'open'
                
        LEFT JOIN User u 
            ON i.operator_id = u.user_id

        WHERE m.status = 'active'

        ORDER BY m.unit_number ASC 
    """)

    return cur.fetchall()

#======================================
# work orders
#======================================


    #open work orders 
def get_open_work_orders(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            wo.work_order_id,
            m.serial_number,
            wo.notes,
            wo.priority,
            wo.created_at
        FROM WorkOrder wo
        JOIN Machine m on wo.machine_id = m.machine_id
        WHERE wo.status = 'open'
            AND wo.assigned_to IS NULL
        ORDER BY wo.priority DESC, wo.created_at ASC
    """)

    return cur.fetchall()

#work orders for assignment 
def get_work_orders_for_assignment(conn, assignment_id):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            wo.work_order_id,
            m.serial_number,
            wo.notes,
            wo.status,
            wo.priority
        FROM WorkOrder wo
        JOIN Machine m ON wo.machine_id = m.machine_id
        WHERE wo.assignment_id = ?
        ORDER BY wo.priority DESC
    """, (assignment_id,))

    return cursor.fetchall()

#foreman creates work orders
def create_manual_work_order(conn, machine_id, foreman_id, notes, priority=1):
    cursor = conn.cursor()

    #verify user is a foreman 
    cursor.execute("""
        SELECT role FROM User WHERE user_id = ?
    """, (foreman_id,))
    row = cursor.fetchone()

    if row is None:
        raise ValueError("User does not exist.")
    
    if row[0] != "foreman":
        raise ValueError("User is not a foreman.")
    
    #verify machine exists
    cursor.execute("""
        SELECT machine_id FROM Machine WHERE machine_id = ?
    """, (machine_id,))

    if cursor.fetchone() is None:
        raise ValueError("Machine does not exist.")
    
     #create work order
    cursor.execute("""
        INSERT INTO WorkOrder (machine_id, created_by, status, priority, notes)
        VALUES (?, ?, 'open', ?, ?)
    """, (machine_id, foreman_id, priority, notes))

    conn.commit()
    return cursor.lastrowid

    
#work orders based on jobs 
def get_work_orders_for_jobs(conn, job_id, include_completed=False):
    cursor = conn.cursor()

    base_sql = """
        SELECT
            wo.work_order_id,
            m.serial_number,
            wo.status,
            wo.priority,
            wo.created_at,
            wo.assigned_to,
            wo.assignment_id,
            wo.notes
        FROM WorkOrder wo
        JOIN Machine m on wo.machine_id = m.machine_id
        WHERE m.current_job_id = ?
    """

    params = [job_id]

    if not include_completed:
        base_sql += " AND  wo.status != 'closed'"

    base_sql += " ORDER BY wo.priority DESC, wo.created_at ASC"

    cursor.execute(base_sql, params)
    return cursor.fetchall()

def get_all_work_orders(conn): 
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            wo.work_order_id,
            wo.assigned_to,
            wo.notes,
            wo.status,
            wo.priority,
            wo.created_at,
            wo.assigned_to,
            
            m.serial_number,
            m.type,
            m.make,
            m.model,
                   
            u.name AS mechanic_name
                   
        FROM WorkOrder wo
        JOIN Machine m
            ON wo.machine_id = m.machine_id
        LEFT JOIN User u
            ON wo.assigned_to = u.user_id
                   
        ORDER BY wo.created_at DESC
    """)

    return cursor.fetchall()

def get_open_machine_fault(conn, machine_id, item_name):
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM MachineFault
        WHERE machine_id = ?
            AND item_name = ?
            AND status = 'open'
        LIMIT 1
    """, (machine_id, item_name))

    return cur.fetchone()

def create_machine_fault(conn, machine_id, item_name):
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO MachineFault (
            machine_id,
            item_name,
            status,
            last_reported_at        
        )
        VALUES (?, ?, 'open', datetime('now'))
    """, (machine_id, item_name))

    conn.commit()

    return cur.lastrowid

def update_machine_fault_last_reported(conn, fault_id):
    cur = conn.cursor()

    cur.execute("""
        UPDATE MachineFault
        SET last_reported_at = datetime('now')
        WHERE fault_id = ?
    """, (fault_id,))

    conn.commit()

def link_fault_to_work_order(conn, fault_id, work_order_id):
    cur = conn.cursor()

    cur.execute("""
        UPDATE MachineFault
        SET work_order_id = ?
        WHERE fault_id = ?
    """, (work_order_id, fault_id))

    conn.commit()
    
def close_machine_fault_for_work_order(conn, work_order_id):
    cur = conn.cursor()

    cur.execute("""
        UPDATE MachineFault
        SET status = 'closed',
            closed_at = datetime('now')
        WHERE work_order_id = ?
            AND status = 'open'
    """, (work_order_id,))

def add_work_order_event(conn, work_order_id, event_type, description, user_id=(None)):
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO WorkOrderEvents (
            work_order_id,
            user_id,
            event_type,
            description    
        )
        VALUES (?, ?, ?, ?)
    """, (
        work_order_id,
        user_id,
        event_type,
        description
    ))

    conn.commit()

def get_work_order_events(conn, work_order_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT
            woe.event_id,
            woe.event_type,
            woe.description,
            woe.created_at,
            u.name,
            u.role
        FROM WorkOrderEvents woe
        LEFT JOIN User u
            ON woe.user_id = u.user_id
        WHERE woe.work_order_id = ?
        ORDER BY woe.created_at DESC
    """, (work_order_id,))

    return cur.fetchall()

def get_work_order_timeline(conn, work_order_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            'comment' AS timeline_type,
            woc.comment_id AS record_id,
            woc.comment AS description,
            woc.created_at,
            u.name AS user_name,
            u.role AS user_role,
            NULL AS event_type
        FROM WorkOrderComment woc
        JOIN User u
            ON woc.user_id = u.user_id
        WHERE woc.work_order_id = ?
        
        UNION ALL
                
        SELECT 
            'event' AS timeline_type,
            woe.event_id AS record_id,
            woe.description AS description,
            woe.created_at,
            u.name AS user_name,
            u.role AS user_role,
            woe.event_type AS event_type
        FROM WorkOrderEvents woe
        LEFT JOIN User u
            ON woe.user_id = u.user_id
        WHERE woe.work_order_id = ?
                
        ORDER BY created_at DESC
    """,(work_order_id, work_order_id))

    return cur.fetchall()



#=====================================
# mechanic assignments
#=====================================


# mechanic assignments compiler
def create_mechanic_assignment(conn, mechanic_id, work_order_ids):
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT role FROM User WHERE user_id = ?
    """, (mechanic_id,))
    row = cursor.fetchone()

    if row is None:
        raise ValueError("User does not exist.")
    
    if row[0] != "mechanic":
        raise ValueError("User is not a mechanic.")
    
    cursor.execute("""
        INSERT INTO MechanicAssignments (mechanic_id)
        VALUES (?)
    """, (mechanic_id,))

    assignment_id = cursor.lastrowid

    for work_order_id in work_order_ids:
        cursor.execute("""
            UPDATE WorkOrder
            SET assigned_to = ?,
                assignment_id = ?,
                status = 'in_progress'
            WHERE work_order_id = ? 
        """, (mechanic_id, assignment_id, work_order_id))

    conn.commit()
    return assignment_id


#assignments for mechanics 
def get_assignments_for_mechanics(conn, mechanic_id):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            ma.assignment_id,
            ma.created_at,
            ma.status
        FROM MechanicAssignments ma
        WHERE ma.mechanic_id = ?
        ORDER BY ma.created_at DESC
    """, (mechanic_id,))

    return cursor.fetchall()


#close assignemnt 
def close_assignment_if_finished(conn, assignment_id):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM WorkOrder
        WHERE assignment_id = ?
            AND status != 'closed'
    """, (assignment_id,))

    remaining = cursor.fetchone()[0]

    if remaining == 0:
        cursor.execute("""
            UPDATE MechanicAssignments
            SET status = 'closed'
            WHERE assignment_id = ?
        """, (assignment_id,))

        conn.commit()

        return True # assignmeent closed
    
    return False #assignment still open

#complete work orders and close assignments 
def complete_work_order(conn, work_order_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT assignment_id
        FROM WorkOrder
        WHERE work_order_id = ?
    """, (work_order_id,))

    row = cur.fetchone()

    if row is None:
        raise ValueError("Work order does not exist.")
    
    assignment_id = row[0]

    cur.execute("""
        UPDATE WorkOrder
        SET status = 'closed',
            completed_at = datetime('now')
        WHERE work_order_id = ?
    """, (work_order_id,))

    add_work_order_event(
        conn,
        work_order_id,
        "work_order_completed",
        f"Work order #{work_order_id} was completed."
    )

    
    close_machine_fault_for_work_order(conn, work_order_id)

    if assignment_id is not None:
        close_assignment_if_finished(conn, assignment_id)

    conn.commit()

def get_work_order_by_id(conn, work_order_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            wo.work_order_id,
            wo.machine_id,
            wo.created_by,
            wo.assigned_to,
            wo.assignment_id,
            wo.status,
            wo.priority,
            wo.created_at,
            wo.completed_at,
            wo.notes,
                
            m.unit_number,
            m.serial_number,
            m.type,
            m.make,
            m.model,

            creator.name AS created_by_name,
            mechanic.name AS assigned_to_name,

            mf.fault_id,
            mf.item_name AS fault_id_name,
            mf.status AS fault_status,
            mf.first_reported_at,
            mf.last_reported_at,
            mf.closed_at AS fault_closed_at
                
        FROM WorkOrder wo
        JOIN Machine m
            ON wo.machine_id = m.machine_id
        JOIN User creator 
            ON wo.created_by = creator.user_id
        LEFT JOIN User mechanic
            ON wo.assigned_to = mechanic.user_id
        LEFT JOIN MachineFault mf
            ON mf.work_order_id = wo.work_order_id
        WHERE wo.work_order_id = ?
    """, (work_order_id,))
    
    return cur.fetchone()

def add_work_order_comment(conn, work_order_id, user_id, comment):
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO WorkOrderComment (
            work_order_id,
            user_id,
            comment
        )
        VALUES (?, ?, ?)
    """, (
        work_order_id,
        user_id,
        comment
    ))

    conn.commit()

def get_work_order_comments(conn, work_order_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            woc.comment_id,
            woc.comment,
            woc.created_at,
            u.user_id,
            u.name,
            u.role
        FROM WorkOrderComment woc
        JOIN User u
            ON woc.user_id = u.user_id
        WHERE woc.work_order_id = ?
        ORDER BY woc.created_at DESC
    """, (work_order_id,))

    return cur.fetchall()



#===================================
# machines
#===================================   

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

#move machine to job
def move_machine_to_job(conn, machine_id, new_job_id):
    cursor = conn.cursor()

    #make sure machine exists
    cursor.execute("""
        SELECT current_job_id FROM Machine WHERE machine_id = ?
    """, (machine_id,))

    row = cursor.fetchone()
    if row is None:
        raise ValueError("Machine does not exist.")
    
    old_job_id = row[0]

    #make sure new job exists
    cursor.execute("""
        SELECT job_id FROM Job WHERE job_id = ?
    """, (new_job_id,))
    if cursor.fetchone() is None:
        raise ValueError("Job does not exist.")
    
    #if currently on that job, do noting 
    if old_job_id == new_job_id:
        return False
    
    #move machine
    cursor.execute("""
        UPDATE Machine 
        SET current_job_id = ?
        WHERE machine_id = ?
    """, (new_job_id, machine_id))

    conn.commit()
    return True #machine moved

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
                j.name
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


#==============================================
# Users
#==============================================

#user checks in
def check_in(conn, user_id, note=""):
    cur = conn.cursor()

    # Prevent double check-in (already checked in with no checkout)
    cur.execute("""
        SELECT shift_id FROM UserShift
        WHERE user_id = ? AND check_out_at IS NULL
        LIMIT 1
    """, (user_id,))
    if cur.fetchone():
        return False  # already checked in

    cur.execute("""
        INSERT INTO UserShift (user_id, note)
        VALUES (?, ?)
    """, (user_id, note))

    conn.commit()
    return True

#user checks out
def check_out(conn, user_id, note=""):
    cur = conn.cursor()

    # Find the open shift
    cur.execute("""
        SELECT shift_id FROM UserShift
        WHERE user_id = ? AND check_out_at IS NULL
        ORDER BY check_in_at DESC
        LIMIT 1
    """, (user_id,))
    row = cur.fetchone()
    if not row:
        return False  # not checked in

    shift_id = row[0]

    cur.execute("""
        UPDATE UserShift
        SET check_out_at = datetime('now'),
            note = CASE
                WHEN ? != '' THEN COALESCE(note || ' | ', '') || ?
                ELSE note
            END
        WHERE shift_id = ?
    """, (note, note, shift_id))

    conn.commit()
    return True

#is user available 
def get_checked_in_users(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT u.user_id, u.name, u.role, s.check_in_at
        FROM UserShift s
        JOIN User u ON u.user_id = s.user_id
        WHERE s.check_out_at IS NULL
          AND u.active = 1
        ORDER BY u.role, u.name
    """)
    return cur.fetchall()

#get mechanics list 
def get_mechanics(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, name, email, active
        FROM User 
        WHERE role = 'mechanic'
            AND active = 1
        ORDER BY name ASC
    """)
    return cur.fetchall()

