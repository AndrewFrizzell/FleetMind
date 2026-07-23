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


def add_work_order_part(
    conn,
    work_order_id,
    part_number,
    description,
    quantity,
    status,
    note,
    part_id=None
):
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO WorkOrderPart (
            work_order_id,
            part_id,
            part_number,
            description,
            quantity,
            status,
            note
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        work_order_id,
        part_id,
        part_number,
        description,
        quantity,
        status,
        note
    ))

    return cur.lastrowid

def get_work_order_parts(conn, work_order_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM WorkOrderPart
        WHERE work_order_id = ?
        ORDER BY created_at DESC
    """, (work_order_id,))

    return cur.fetchall()

def update_work_order_part_status(conn, work_order_part_id, status):
    cur = conn.cursor()

    cur.execute("""
        UPDATE WorkOrderPart
        SET status = ?
        WHERE work_order_part_id = ?
    """, (status, work_order_part_id))

    conn.commit()

def get_work_order_part_by_id(conn, work_order_part_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            wop.*,
            wo.machine_id,
            m.unit_number,
            m.make,
            m.model,
            m.year,
            m.serial_number,
            m.vin_number
        FROM WorkOrderPart wop
                
        JOIN WorkOrder wo
            ON wop.work_order_id = wo.work_order_id
        
        JOIN Machine m
            ON wo.machine_id = m.machine_id
                
        WHERE work_order_part_id = ?
    """, (work_order_part_id,))

    return cur.fetchone()

def get_all_work_order_parts(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            p.part_id,
            p.work_order_id,
            p.part_number,
            p.description,
            p.quantity,
            p.status,
            p.note,
            p.created_at,
                
            wo.status AS work_order_status,
                
            m.machine_id,
            m.unit_number,
            m.make,
            m.model
                
        FROM WorkOrderPart p 
        JOIN WorkOrder wo
            ON p.work_order_id = wo.work_order_id
        JOIN Machine m
            ON wo.machine_id = m.machine_id
        ORDER BY 
            wo.created_at DESC,
            CASE p.status
                WHEN 'needed' THEN 1
                WHEN 'ordered' THEN 2
                WHEN 'received' THEN 3
                WHEN 'installed' then 4
                ELSE 5
            END,
            p.created_at DESC
    """)

    return cur.fetchall()

def get_open_part_requests(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            wop.*,
            wo.work_order_id,
            wo.status AS work_order_status,
            wo.work_order_type,
            m.machine_id,
            m.unit_number,
            m.make,
            m.model
        FROM WorkOrderPart wop
        JOIN WorkOrder wo
            ON wop.work_order_id = wo.work_order_id
        JOIN Machine m
            ON wo.machine_id = m.machine_id
        WHERE wop.status != 'installed'
        ORDER BY wop.created_at DESC
    """)

    return cur.fetchall()

def update_work_order_part_details(
        conn,
        work_order_part_id,
        part_number,
        description,
        quantity,
        status,
        note
):
    cur = conn.cursor()

    cur.execute("""
        UPDATE WorkOrderPart
        SET part_number = ?,
            description = ?,
            quantity = ?,
            status = ?,
            note = ?
        WHERE work_order_part_id = ?
    """, (
        part_number,
        description,
        quantity,
        status,
        note,
        work_order_part_id
    ))

    conn.commit()

def link_catalog_part_to_request(
    conn,
    work_order_part_id,
    catalog_part_id
):
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM Part
        WHERE part_id = ?
            AND active = 1
    """, (catalog_part_id,))

    catalog_part = cur.fetchone()

    if catalog_part is None:
        raise ValueError("Catalog part not found.")
    
    cur.execute("""
        UPDATE WorkOrderPart
        SET part_id = ?,
            part_number = ?,
            description = ?
        WHERE work_order_part_id = ?
    """, (
        catalog_part["part_id"],
        catalog_part["part_number"],
        catalog_part["name"],
        work_order_part_id
    ))

    conn.commit()

def add_part_machine_campatibility(conn, part_id, machine_id):
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO PartMachineCompatibility(
            part_id,
            machine_id        
        )
        VALUES (?, ?)
    """, (
        part_id,
        machine_id
    ))

    conn.commit()

def add_part_machine_compatibilities(conn, part_id, machine_ids):
    cur = conn.cursor()

    for machine_id in machine_ids:
        cur.execute("""
            INSERT OR IGNORE INTO PartMachineCompatibility (
                part_id,
                machine_id        
            )
            VALUES (?, ?)
        """, (
            part_id,
            machine_id
        ))

def get_catalog_part_by_id(conn, part_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.*
        FROM Part p
        WHERE p.part_id = ?
    """, (part_id,))

    return cur.fetchone()

def get_compatible_machines_for_part(conn, part_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT
            m.machine_id,
            m.unit_number,
            m.year,
            m.make,
            m.model,
            m.serial_number,
            m.vin_number,
            m.status,
            m.operational_state
        FROM PartMachineCompatibility pmc
                
        JOIN Machine m
            ON pmc.machine_id = m.machine_id
        
        WHERE pmc.part_id = ?
            AND m.active = 1
                
        ORDER BY 
            m.unit_number
    """, (part_id,))

    return cur.fetchall()

def get_part_request_history(conn, part_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT
            wop.work_order_part_id,
            wop.work_order_id,
            wop.description,
            wop.quantity,
            wop.status,
            wop.part_number,
            wop.note,
                
            wo.status AS work_order_status,
            wo.priority,
            wo.created_at,
            wo.completed_at,
                
            m.machine_id,
            m.unit_number,
            m.make,
            m.model,
            m.serial_number
                
        FROM WorkOrderPart wop
                
        JOIN WorkOrder wo
            ON wop.work_order_id = wo.work_order_id
                
        JOIN Machine m
            ON wo.machine_id = m.machine_id
        
        where wop.part_id = ?
                
        ORDER BY 
            wo.created_at DESC,
            wop.work_order_part_id DESC
    """, (part_id,))

    return cur.fetchall()


    
