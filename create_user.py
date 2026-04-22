from fleetmind_db import get_connection

def create_user(name, role, email, password):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO User (name, role, email, password_hash, active)
        VALUES (?, ?, ?, ?, 1)
    """, (name, role, email.lower().strip(), password))

    conn.commit()
    conn.close()
    print("User created:", email)

if __name__ == "__main__":
    # Change these to whatever you want:
    create_user(
        name="Eddie Manager",
        role="equipment_manager",
        email="manager2@fleetmind.com",
        password="password123"
    )
