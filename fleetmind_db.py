import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "fleetmind.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def create_tables(conn):
    cursor = conn.cursor()

    # User table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS User (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('operator', 'foreman', 'equipment_manager', 'mechanic')),
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1
    );
    """)

    # Job table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Job(
        job_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        location TEXT,
        foreman_id INTEGER NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (foreman_id) REFERENCES User(user_id)
    );
    """)

    # Machine table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Machine (
        machine_id INTEGER PRIMARY KEY,
        serial_number TEXT UNIQUE NOT NULL,
        type TEXT NOT NULL,
        make TEXT,
        model TEXT,
        year INTEGER,
        status TEXT NOT NULL CHECK (status IN ('active', 'inactive', 'out_of_service')),
        operational_state TEXT NOT NULL DEFAULT 'running'
            CHECK (operational_state IN ('running', 'down')),
        current_job_id INTEGER,
        FOREIGN KEY (current_job_id) REFERENCES Job(job_id)
                   
    );
    """)

    # Master checklist items
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS MasterCheckListItem (
        item_id INTEGER PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        active INTEGER NOT NULL DEFAULT 1
    );
    """)

    # Checklist template
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ChecklistTemplate (
        template_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_by INTEGER NOT NULL,
        FOREIGN KEY (created_by) REFERENCES User(user_id)
    );
    """)

    # Inspections
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Inspections (
        inspection_id INTEGER PRIMARY KEY AUTOINCREMENT,
        machine_id INTEGER NOT NULL,
        operator_id INTEGER NOT NULL,
        inspection_date TEXT DEFAULT (datetime('now')),
        notes TEXT,
        passed INTEGER DEFAULT 1,
        FOREIGN KEY (machine_id) REFERENCES Machine(machine_id),
        FOREIGN KEY (operator_id) REFERENCES User(user_id)
    );
    """)

    # Work orders
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS WorkOrder (
        work_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        machine_id INTEGER NOT NULL,
        created_by INTEGER NOT NULL,
        assigned_to INTEGER,
        assignment_id INTEGER,
        status TEXT DEFAULT 'open',
        priority INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now')),
        completed_at TEXT,
        notes TEXT,
        FOREIGN KEY (machine_id) REFERENCES Machine(machine_id),
        FOREIGN KEY (created_by) REFERENCES User(user_id),
        FOREIGN KEY (assigned_to) REFERENCES User(user_id)
        FOREIGN KEY (assignment_id) REFERENCES MechanicAssignments(assignment_id)
    );
    """)

    # Template items
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS TemplateItems (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER NOT NULL,
        description TEXT NOT NULL,
        required INTEGER DEFAULT 1,
        FOREIGN KEY (template_id) REFERENCES ChecklistTemplate(template_id)
    );
    """)

    # Mechanic assignments
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS MechanicAssignments (
        assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        mechanic_id INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        status TEXT DEFAULT 'open',
        FOREIGN KEY (mechanic_id) REFERENCES User(user_id)
    );
    """)

    #user availablity 
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS UserShift (
        shift_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        check_in_at TEXT NOT NULL DEFAULT (datetime('now')),
        check_out_at TEXT,
        note TEXT,
        FOREIGN KEY (user_id) REFERENCES User(user_id)
    );
    """)

    conn.commit()

if __name__ == "__main__":
    conn = get_connection()
    create_tables(conn)
    conn.close()
    print("Database updated successfully")
