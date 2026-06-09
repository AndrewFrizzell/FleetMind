from fleetmind_db import get_connection

def column_exists(conn, table_name, column_name):
    cur = conn.cursor()

    cur.execute(f"PRAGMA table_info({table_name})")
    columns = cur.fetchall()

    return any(column["name"] == column_name for column in columns)

def add_column_if_missing(conn, table_name, column_name, column_sql):
    if column_exists(conn, table_name, column_name):
        print(f"{table_name}.{column_name} already exists.")
        return
    
    cur = conn.cursor()
    cur.execute(f"""
        ALTER TABLE {table_name}
        ADD COLUMN {column_sql}
    """)

    conn.commit()
    print(f"Added {table_name}.{column_name}.")

def main():
    conn = get_connection()

    add_column_if_missing(
        conn,
        "MachineFault",
        "operator_decision",
        "operator_decision TEXT"
    )

    conn.close()
    print("Migrations complete.")

if __name__ == "__main__":
    main()