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
    CREATE TABLE IF NOT EXISTS Job (
        job_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        location TEXT,
        foreman_id INTEGER NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (foreman_id) REFERENCES User(user_id)
    );
    """)

    #job events 
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS JobEvent (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        user_id INTEGER,
        event_type TEXT NOT NULL,
        description TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),

        FOREIGN KEY (job_id) REFERENCES Job(job_id),
        FOREIGN KEY (user_id) REFERENCES User(user_id)             
    );
    """)

    # Machine table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Machine (
        machine_id INTEGER PRIMARY KEY AUTOINCREMENT,
        unit_number TEXT UNIQUE NOT NULL,
        department TEXT NOT NULL,
        serial_number TEXT UNIQUE,
        vin_number TEXT UNIQUE,
        type TEXT NOT NULL,
        make TEXT,
        model TEXT,
        year INTEGER,
        meter_type TEXT NOT NULL
            CHECK (meter_type IN ('miles', 'hours')),
        current_meter_reading REAL NOT NULL DEFAULT 0,
        status TEXT NOT NULL CHECK (status IN ('active', 'inactive', 'out_of_service')),
        operational_state TEXT NOT NULL DEFAULT 'running'
            CHECK (operational_state IN ('running',
                                        'running_with_faults',
                                        'down')),
        photo_url TEXT,
        current_job_id INTEGER,
        active INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (current_job_id) REFERENCES Job(job_id)
    );
    """)

    # Master checklist items
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS MasterChecklistItem (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        active INTEGER NOT NULL DEFAULT 1
    );
    """)

    #machine-specific checklist items
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS MachineChecklistItem (
        machine_checklist_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        machine_id INTEGER NOT NULL,
        master_item_id INTEGER NOT NULL,
        required INTEGER NOT NULL DEFAULT 1,
        active INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (machine_id) REFERENCES Machine(machine_id),
        FOREIGN KEY (master_item_id) REFERENCES MasterChecklistItem(item_id),
        UNIQUE(machine_id, master_item_id)
    );
    """)

    # Checklist template
 #   cursor.execute("""
  #  CREATE TABLE IF NOT EXISTS ChecklistTemplate (
  #      template_id INTEGER PRIMARY KEY AUTOINCREMENT,
  #      name TEXT NOT NULL,
  #      created_by INTEGER NOT NULL,
  #      FOREIGN KEY (created_by) REFERENCES User(user_id)
  #  );
  #  """)

    # Template items
#    cursor.execute("""
 #   CREATE TABLE IF NOT EXISTS TemplateItems (
 #      item_id INTEGER PRIMARY KEY AUTOINCREMENT,
 #       template_id INTEGER NOT NULL,
 #       description TEXT NOT NULL,
 #       required INTEGER NOT NULL DEFAULT 1,
 #       FOREIGN KEY (template_id) REFERENCES ChecklistTemplate(template_id)
 #   );
 #   """)

    # Inspections
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Inspections (
        inspection_id INTEGER PRIMARY KEY AUTOINCREMENT,
        machine_id INTEGER NOT NULL,
        operator_id INTEGER NOT NULL,
        job_id INTEGER,
        inspection_date TEXT NOT NULL DEFAULT (datetime('now')),
        
        status TEXT NOT NULL DEFAULT 'open',
        opening_meter REAL,
        closing_meter REAL,
        closed_at TEXT,
                   
        notes TEXT,
        passed INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (machine_id) REFERENCES Machine(machine_id),
        FOREIGN KEY (operator_id) REFERENCES User(user_id),
        FOREIGN KEY (job_id) REFERENCES Job(job_id)
    );
    """)

    # Inspection items
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS InspectionItems (
        inspection_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        inspection_id INTEGER NOT NULL,
        item_name TEXT NOT NULL,
        passed INTEGER NOT NULL DEFAULT 1,
        operator_decision TEXT,
        inspection_phase TEXT NOT NULL DEFAULT 'opening',
        created_work_order INTEGER NOT NULL DEFAULT 0,
        note TEXT,
        FOREIGN KEY (inspection_id) REFERENCES Inspections(inspection_id)
    );
    """)


    # Work orders
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS WorkOrder (
        work_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        machine_id INTEGER NOT NULL,
        created_by INTEGER NOT NULL,
        assigned_to INTEGER,
        status TEXT NOT NULL DEFAULT 'open'
            CHECK (status IN ('open',
                'assigned',
                'in_progress',
                'waiting_on_parts',
                'repair_complete',
                'closed'
            )),
        priority INTEGER NOT NULL DEFAULT 1
            CHECK (priority IN (1, 2, 3)),
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        completed_at TEXT,
        work_order_type TEXT NOT NULL DEFAULT 'repair',
        maintenance_id INTEGER,
        notes TEXT,
                   

        FOREIGN KEY (machine_id) REFERENCES Machine(machine_id),
        FOREIGN KEY (created_by) REFERENCES User(user_id),
        FOREIGN KEY (assigned_to) REFERENCES User(user_id)
    );
    """)

    #work order comments 
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS WorkOrderComment(
        comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        work_order_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        comment TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        
        FOREIGN KEY (work_order_id) REFERENCES WorkOrder(work_order_id),
        FOREIGN KEY (user_id) REFERENCES User(user_id)
    );
    """)

    #work order events 
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS WorkOrderEvents(
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        work_order_id INTEGER NOT NULL,
        user_id INTEGER,
        event_type TEXT NOT NULL,
        description TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        
        FOREIGN KEY (work_order_id) REFERENCES WorkOrder(work_order_id),
        FOREIGN KEY (user_id) REFERENCES User(user_id)
    );    
    """)

    # User shifts
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


    #machine faults 
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS MachineFault (
        fault_id INTEGER PRIMARY KEY AUTOINCREMENT,
        machine_id INTEGER NOT NULL,
        item_name TEXT NOT NULL,
        operator_decision TEXT,
        status TEXT NOT NULL DEFAULT 'open',
        first_reported_at TEXT NOT NULL DEFAULT (datetime('now')),
        last_reported_at TEXT,
        work_order_id INTEGER,
        closed_at TEXT,
                   
        FOREIGN KEY (machine_id) REFERENCES Machine(machine_id),
        FOREIGN KEY (work_order_id) REFERENCES WorkOrder(work_order_id),
                   
        UNIQUE(machine_id, item_name, status)
        
    );
    """)

    conn.commit()

    #work order parts table 
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS WorkOrderPart (
        work_order_part_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   
        work_order_id INTEGER NOT NULL,
        part_id INTEGER,
        
        part_number TEXT,
        description TEXT NOT NULL,
        quantity REAL NOT NULL DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'needed',
        note TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        
        FOREIGN KEY (work_order_id) REFERENCES WorkOrder(work_order_id),
        FOREIGN KEY (part_id) REFERENCES Part(part_id)
    );
    """)

    #machine maintence items 
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS MaintenanceSchedule (
            maintenance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id INTEGER NOT NULL,

            name TEXT NOT NULL,
            description TEXT,

            interval_type TEXT NOT NULL
                CHECK (interval_type IN ('hours', 'miles', 'days')),

            interval_value REAL NOT NULL,

            last_completed_meter REAL,
            last_completed_date TEXT,

            next_due_meter REAL,
            next_due_date TEXT,
                   
            open_work_order_id INTEGER,

            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),

            FOREIGN KEY (machine_id) REFERENCES Machine(machine_id),
            FOREIGN KEY (open_work_order_id) REFERENCES Workorder(work_order_id),

            UNIQUE(machine_id, name)    
            );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Part (
        part_id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_number TEXT,
        name TEXT NOT NULL,
        description TEXT,
        manufacturer TEXT,
        unit_of_measure TEXT DEFAULT 'each',
        default_cost REAL,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS PartMachineCompatibility (
        part_machine_compatibility_id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_id INTERGER NOT NULL,
        machine_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (part_id) REFERENCES Part(part_id),
        FOREIGN KEY (machine_id) REFERENCES Machine(machine_id),

        UNIQUE(part_id, machine_id)          
    );
    """)


if __name__ == "__main__":
    conn = get_connection()   
    create_tables(conn)
    conn.close()
    print("Database updated successfully")