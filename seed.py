from fleetmind_db import get_connection, create_tables


def clear_tables(conn):
    cur = conn.cursor()

    tables = [
        "InspectionItems",
        "Inspections",
        "WorkOrder",
        "MachineChecklistItem",
        #"TemplateItems",
        #"ChecklistTemplate",
        "MasterChecklistItem",
        "Machine",
        "Job",
        "UserShift",
        "User",
    ]

    for table in tables:
        cur.execute(f"DELETE FROM {table}")

    conn.commit()


def seed_users(conn):
    cur = conn.cursor()

    users = [
        ("Operator One", "operator", "operator@test.com", "pass"),
        ("Foreman One", "foreman", "foreman@test.com", "pass"),
        ("Equipment Manager", "equipment_manager", "manager@test.com", "pass"),
        ("Mechanic One", "mechanic", "mechanic@test.com", "pass"),
        ("Mechanic Two", "mechanic", "mechanic2@test.com", "pass"),
    ]

    cur.executemany("""
        INSERT INTO User (name, role, email, password_hash)
        VALUES (?, ?, ?, ?)
    """, users)

    conn.commit()


def seed_jobs(conn):
    cur = conn.cursor()

    foreman = cur.execute("""
        SELECT user_id FROM User
        WHERE role = 'foreman'
        LIMIT 1
    """).fetchone()

    cur.execute("""
        INSERT INTO Job (name, location, foreman_id)
        VALUES (?, ?, ?)
    """, ("Main Street Project", "Seguin, TX", foreman["user_id"]))

    conn.commit()


def seed_master_checklist(conn):
    cur = conn.cursor()

    checklist_items = [
        ("Engine oil level", "Check engine oil before use."),
        ("Coolant level", "Check coolant level and leaks."),
        ("Hydraulic leaks", "Inspect hoses, cylinders, and fittings."),
        ("Tires or tracks", "Check condition and damage."),
        ("Lights", "Verify work lights and signals operate."),
        ("Horn", "Verify horn works."),
        ("Backup alarm", "Verify backup alarm works."),
        ("Brakes", "Check brake operation."),
        ("Seat belt", "Check seat belt condition."),
        ("Fire extinguisher", "Verify present and charged."),
    ]

    cur.executemany("""
        INSERT OR IGNORE INTO MasterChecklistItem (name, description)
        VALUES (?, ?)
    """, checklist_items)

    conn.commit()


def main():
    conn = get_connection()

    create_tables(conn)
    clear_tables(conn)

    seed_users(conn)
    seed_jobs(conn)
    seed_master_checklist(conn)

    conn.close()
    print("Seed complete.")


if __name__ == "__main__":
    main()