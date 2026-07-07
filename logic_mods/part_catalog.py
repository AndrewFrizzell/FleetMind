def create_part(
        conn,
        part_number,
        name,
        description=None,
        manufacturer=None,
        unit_of_measure="each",
        default_cost=None
):
    cur = conn.cursor()

    part_number = (part_number or "").strip().upper()
    name = (name or "").strip()
    description = (description or "").strip()
    manufacturer = (manufacturer or "").strip().upper()
    unit_of_measure = (unit_of_measure or "each").strip().lower()

    cur.execute("""
        INSERT INTO Part(
            part_number,
            name,
            description,
            manufacturer,
            unit_of_measure,
            default_cost       
        )
        VALUES (?, ?, ?, ?, ?, ?, )
    """, (
        part_number,
        name,
        description,
        manufacturer,
        unit_of_measure,
        default_cost
    ))

    conn.commit()
    return cur.lastrowid

def get_all_parts_by_id(conn, part_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM Part
        WHERE part_id = ?
    """, (part_id,))

    return cur.fetchone()

def get_all_parts(conn):
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM Part
        WHERE active = 1
        ORDER BY name ASC, part_number ASC
    """)

    return cur.fetchall()

def search_parts(conn, search_term):
    cur = conn.cursor()

    term = f"%(search_term.strip())%"

    cur.execute("""
        SELECT *
        FROM Part
        WHERE active = 1
            AND (
                part_number LIKE ?
                OR name LIKE ?
                OR description LIKE ?
                OR manufacturer LIKE ?    
            )
        ORDER BY name ASC, part_number ASC
    """, (
        term,
        term,
        term,
        term
    ))

    return cur.fetchall()
    
def find_existing_part(conn, part_number, name):
    cur = conn.cursor()

    part_number = (part_number or "").strip().upper()
    name = (name or "").strip()

    if part_number:
        cur.execute("""
            SELECT *
            FROM Part
            WHERE active = 1
                AND part_number = ?
            LIMIT 1
        """, (part_number,))

        part = cur.fetchone()
    
        if part:
            return part

    cur.execute("""
        SELECT *
        FROM Part
        WHERE active = 1
            AND lower(name) = lower(?)
        LIMIT 1
    """, (name,))

    return cur.fetchone()