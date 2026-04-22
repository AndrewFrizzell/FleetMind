#creates inspections 
def create_inspection(conn, machine_id, operator_id, results, notes=""):
    cursor = conn.cursor()

    # Create inspection
    cursor.execute("""
        INSERT INTO Inspections (machine_id, operator_id, notes, passed)
        VALUES (?, ?, ?, ?)
    """, (machine_id, operator_id, notes, int(all(results.values()))))

    inspection_id = cursor.lastrowid

    # Loop through checklist results
    for item_id, passed in results.items():

        # Auto-create work order if failed
        if not passed:
            cursor.execute("""
                INSERT INTO WorkOrder (machine_id, created_by, status, priority, notes)
                VALUES (?, ?, 'open', 2, ?)
            """, (
                machine_id,
                operator_id,
                f"Auto-created from failed inspection item {item_id}"
            ))

    conn.commit()
    return inspection_id

#creates work orders from inspections
def assign_work_orders(conn, work_order_ids, mechanic_id):
    cursor = conn.cursor()

    # Verify mechanic exists and is a mechanic
    cursor.execute("""
        SELECT role FROM User WHERE user_id = ?
    """, (mechanic_id,))
    row = cursor.fetchone()

    if row is None:
        raise ValueError("User does not exist.")

    if row[0] != "mechanic":
        raise ValueError("User is not a mechanic.")

    # Assign work orders
    for work_order_id in work_order_ids:
        cursor.execute("""
            UPDATE WorkOrder
            SET assigned_to = ?, status = 'in_progress'
            WHERE work_order_id = ?
        """, (mechanic_id, work_order_id))

    conn.commit()

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

#open work orders 
def get_open_work_orders(conn):
    cursor = conn.cursor()

    cursor.execute("""
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

    return cursor.fetchall()

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

#close assignemnt 
def close_assignment_if_finished(conn, assignment_id):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM WorkOrder
        WHERE assignment_id = ?
            AND status != 'completed'
    """, (assignment_id,))

    remaining = cursor.fetchone()[0]

    if remaining == 0:
        cursor.execute("""
            UPDATE MechanicAssignments
            SET status = 'completed'
            WHERE assignment_id = ?
        """, (assignment_id,))

        conn.commit()

        return True # assignmeent closed
    
    return False #assignment still open

#complete work orders and close assignments 
def complete_work_order(conn, work_order_id):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT assignment_id
        FROM WorkOrder
        WHERE work_order_id = ?
    """, (work_order_id,))
    row = cursor.fetchone()
    if row is None:
        raise ValueError("Work order does not exist.")
    assignment_id = row[0]

    cursor.execute("""
        UPDATE WorkOrder
        SET status = 'completed'
        WHERE work_order_id = ?
    """, (work_order_id,))

    if assignment_id is not None:
        close_assignment_if_finished(conn, assignment_id)

    conn.commit()

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
        base_sql += " AND  wo.status != 'completed'"

    base_sql += " ORDER BY wo.priority DESC, wo.created_at ASC"

    cursor.execute(base_sql, params)
    return cursor.fetchall()

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

#get machine list 
def get_all_machines(conn, include_inactive=True):
    cur = conn.cursor()
    
    if include_inactive:
        cur.execute("""
            SELECT
                m.machine_id,
                m.serial_number,
                m.type,
                m.make,
                m.model,
                m.year,
                m.status,
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
                m.serial_number,
                m.type,
                m.make,
                m.model,
                m.year,
                m.status,
                m.current_job_id,
                j.name
            FROM Machine m
            LEFT JOIN Job j ON m.current_job_id = j.job_id
            WHERE m.status = 'active'
            ORDER BY m.serial_number ASC
        """)

    return cur.fetchall()
        
    
