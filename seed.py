import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "fleetmind.db")

def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    # Clear data (order matters with FK)
    for t in [
    "WorkOrder",
    "InspectionItems",
    "Inspections",
    "Machine",
    "Job",
    "TemplateItems",
    "ChecklistTemplate",
    "MasterChecklistItem",
    "MechanicAssignments",
    "UserShift",
    "User"
    ]:
        try:
            cur.execute(f"DELETE FROM {t};")
        except sqlite3.OperationalError:
            pass

    # 1) Users
    user_rows = [
        ("Operator One", "operator", "op1@fleetmind.test", "hash_op1", 1),
        ("Operator Two", "operator", "op2@fleetmind.test", "hash_op2", 1),
        ("Manager One", "equipment_manager", "mgr1@fleetmind.test", "hash_mgr1", 1),
        ("Mechanic One", "mechanic", "mech1@fleetmind.test", "hash_mech1", 1),
        ("Foreman One", "foreman", "fore1@fleetmind.test", "hash_fore1", 1),
    ]
    cur.executemany(
        "INSERT INTO User (name, role, email, password_hash, active) VALUES (?, ?, ?, ?, ?);",
        user_rows
    )

    def get_user_id(email):
        row = cur.execute("SELECT user_id FROM User WHERE email = ?;", (email,)).fetchone()
        return row["user_id"]

    op1_id = get_user_id("op1@fleetmind.test")
    op2_id = get_user_id("op2@fleetmind.test")
    mgr1_id = get_user_id("mgr1@fleetmind.test")
    mech1_id = get_user_id("mech1@fleetmind.test")
    fore1_id = get_user_id("fore1@fleetmind.test")

    # 2) Job (needs foreman_id)
    cur.execute(
        "INSERT INTO Job (name, location, foreman_id, active) VALUES (?, ?, ?, ?);",
        ("Downtown Site", "Chicago, IL", fore1_id, 1)
    )
    job_id = cur.lastrowid

    # 3) Machines (machines can exist without job; we’ll set 1 with job, 1 without)
    machine_rows = [
        (101, "SN-EX-100", "Excavator", "CAT", "320", 2021, "active", job_id),
        (102, "SN-SK-200", "Skid Steer", "Bobcat", "S650", 2020, "active", None),
        (103, "SN-DT-300", "Dump Truck", "Ford", "F-750", 2019, "inactive", None),
    ]
    cur.executemany(
        """
        INSERT INTO Machine (machine_id, serial_number, type, make, model, year, status, current_job_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        machine_rows
    )

    # 4) Inspection (one fail-ish via passed=0)
    cur.execute(
        """
        INSERT INTO Inspections (machine_id, operator_id, notes, passed)
        VALUES (?, ?, ?, ?);
        """,
        (101, op1_id, "Hydraulic leak seen near boom cylinder", 0)
    )
    insp1_id = cur.lastrowid

    cur.execute(
        """
        INSERT INTO Inspections (machine_id, operator_id, notes, passed)
        VALUES (?, ?, ?, ?);
        """,
        (102, op2_id, "All good", 1)
    )

    # 5) WorkOrder (created_by required; assigned_to optional)
    cur.execute(
    """
    INSERT INTO WorkOrder (machine_id, created_by, assigned_to, status, priority, notes)
    VALUES (?, ?, ?, ?, ?, ?);
    """,
    (101, mgr1_id, None, "open", 3, f"From inspection {insp1_id}: fix hydraulic leak.")
    )
    #6) chekclist items
    checklist_items = [
        ("Engine Oil", "Check engine oil level and leaks", 1),
        ("Coolant", "Check coolant level and visible leaks", 1),
        ("Hydraulic Fluid", "Check hydraulic fluid and leaks", 1),
        ("Tires/Tracks", "Inspect tires or tracks for damage", 1),
        ("Lights", "Check all lights", 1),
        ("Horn/Backup Alarm", "Check horn and backup alarm", 1),
        ("Brakes", "Check brake operation", 1),
        ("Leaks", "Look for visible leaks under machine", 1),
    ]

    cur.executemany(
        """
        INSERT INTO MasterChecklistItem (name, description, active)
        VALUES (?, ?, ?);
        """,
        checklist_items
    )



    conn.commit()
    conn.close()
    print("✅ Seed complete.")

if __name__ == "__main__":
    seed()
