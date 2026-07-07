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

    conn.commit()

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
        SELECT *
        FROM WorkOrderPart
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
