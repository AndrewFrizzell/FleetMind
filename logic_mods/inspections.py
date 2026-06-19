from logic_mods.work_orders import(
    get_open_machine_fault,
    create_machine_fault,
    update_machine_fault_last_reported,
    add_work_order_event,
    link_fault_to_work_order
)

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