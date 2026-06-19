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

def create_open_inspection(conn, machine_id, operator_id, opening_meter=None, notes=None, job_id=None):
    existing_inspection = get_open_inspection_for_machine(conn, machine_id)

    if existing_inspection:
        return existing_inspection
    
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO Inspections (
            machine_id,
            operator_id,
            job_id,
            opening_meter,
            notes,
            status,
            passed    
            )
        VALUES (?, ?, ?, ?, ?, 'open', 1)
    """,(machine_id, 
         operator_id, 
         job_id,
         opening_meter, 
         notes
         
         ))

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

    for item_name, data in results.items():
        passed = data["passed"]
        note = data.get("note", "")
        operator_decision = data.get("operator_decision")

        cur.execute("""
            INSERT INTO InspectionItems (
                inspection_id,
                item_name,
                passed,
                operator_decision,
                note
            )
            VALUES (?, ?, ?, ?, ?)
        """, (inspection_id,
              item_name,
              int(passed),
              operator_decision,
              note
              
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
                    item_name,
                    operator_decision
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
        int(all(data["passed"] for data in results.values())),
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

def get_inspection_by_id(conn, inspection_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            i.inspection_id,
            i.machine_id,
            i.operator_id,
            i.job_id,
            i.inspection_date,
            i.status,
            i.opening_meter,
            i.closing_meter,
            i.closed_at,
            i.notes,
            i.passed,

            m.unit_number,
            m.serial_number,
            m.make,
            m.model,
            m.type,
                
            u.name AS operator_name,
                
            j.name AS job_name
        FROM Inspections i 
        JOIN Machine m
            ON i.machine_id = m.machine_id
        JOIN User u
            ON i.operator_id = u.user_id
        LEFT JOIN Job j
            ON i.job_id = j.job_id
        WHERE i.inspection_id = ?
    """, (inspection_id,))

    return cur.fetchone()

def get_inspection_items(conn, inspection_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT
            inspection_item_id,
            item_name,
            passed,
            operator_decision,
            inspection_phase,
            created_work_order,
            note
        FROM InspectionItems
        WHERE inspection_id = ?
        ORDER BY item_name ASC
    """, (inspection_id,))

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
    cur = conn.cursor()

    cur.execute("""
        SELECT
            wo.work_order_id,
            wo.assigned_to,
            wo.notes,
            wo.status,
            wo.priority,
            wo.created_at,
            wo.assigned_to,
            
            m.unit_number,
            m.machine_id,
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
                   
        ORDER BY 
        CASE wo.status
            WHEN 'repair_complete' THEN 1
            WHEN 'waiting_on_parts' THEN 2
            WHEN 'in_progress' THEN 3
            WHEN 'assigned' THEN 4
            WHEN 'open' THEN 5
            WHEN 'closed' THEN 6
        END,
        wo.created_at DESC
    """)

    return cur.fetchall()

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

def create_machine_fault(conn, machine_id, item_name, operator_decision=None):
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO MachineFault (
            machine_id,
            item_name,
            operator_decision,
            status,
            last_reported_at        
        )
        VALUES (?, ?, ?, 'open', datetime('now'))
    """, (machine_id, item_name, operator_decision))

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

    conn.commit()

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











def update_work_order_status(conn, work_order_id, new_status):
    allowed_statuses = [
        "open",
        "assigned",
        "in_progress",
        "waiting_on_parts",
        "repair_complete",
        "closed"
    ]

    if new_status not in allowed_statuses:
        raise ValueError("Invalid work order status.")
    
    cur = conn.cursor()

    cur.execute("""
        UPDATE WorkOrder
        SET status = ?
        WHERE work_order_id = ?
    """, (
        new_status,
        work_order_id
    ))

    conn.commit()

def get_work_order_status_counts(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT
            status,
            COUNT(*) AS count
        FROM WorkOrder
        GROUP BY status
    """)

    rows = cur.fetchall()

    counts = {
        "open": 0,
        "assigned": 0,
        "in_progress": 0,
        "waiting_on_parts": 0,
        "repair_complete": 0,
        "closed": 0
    }

    for row in rows:
        counts[row["status"]] = row["count"]

    return counts

def assign_work_order_mechanic(conn, work_order_id, mechanic_id):
    cur = conn.cursor()

    cur.execute("""
        UPDATE WorkOrder
        SET assigned_to = ?,
            status = CASE
                WHEN status = 'open' Then 'assigned'
                ELSE status
            END
        WHERE work_order_id = ?
    """, (
        mechanic_id,
        work_order_id
    ))

    conn.commit()





#=====================================
# mechanic assignments
#=====================================




def get_work_orders_for_mechanic(conn, mechanic_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            wo.work_order_id,
            wo.machine_id,
            wo.status,
            wo.priority,
            wo.notes,
            wo.created_at,
                
            m.unit_number,
            m.make,
            m.model
        FROM WorkOrder wo
        JOIN Machine m
            ON wo.machine_id = m.machine_id
        WHERE wo.assigned_to = ?
            AND wo.status != 'closed'
        ORDER BY 
            CASE wo.status
                WHEN 'assigned' THEN 1
                WHEN 'in_progress' THEN 2
                WHEN 'waiting_on_parts' THEN 3
                WHEN 'repair_complete' THEN 4
                ELSE 5
            END,
            wo.created_at DESC
    """, (mechanic_id,))

    return cur.fetchall()

def get_work_order_by_id(conn, work_order_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            wo.work_order_id,
            wo.machine_id,
            wo.created_by,
            wo.assigned_to,
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
            mf.item_name AS fault_item_name,
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









        



























