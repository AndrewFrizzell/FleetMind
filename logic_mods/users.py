#user checks in
def check_in(conn, user_id, note=""):
    cur = conn.cursor()

    # Prevent double check-in (already checked in with no checkout)
    cur.execute("""
        SELECT shift_id FROM UserShift
        WHERE user_id = ? AND check_out_at IS NULL
        LIMIT 1
    """, (user_id,))
    if cur.fetchone():
        return False  # already checked in

    cur.execute("""
        INSERT INTO UserShift (user_id, note)
        VALUES (?, ?)
    """, (user_id, note))

    conn.commit()
    return True

#user checks out
def check_out(conn, user_id, note=""):
    cur = conn.cursor()

    # Find the open shift
    cur.execute("""
        SELECT shift_id FROM UserShift
        WHERE user_id = ? AND check_out_at IS NULL
        ORDER BY check_in_at DESC
        LIMIT 1
    """, (user_id,))
    row = cur.fetchone()
    if not row:
        return False  # not checked in

    shift_id = row[0]

    cur.execute("""
        UPDATE UserShift
        SET check_out_at = datetime('now'),
            note = CASE
                WHEN ? != '' THEN COALESCE(note || ' | ', '') || ?
                ELSE note
            END
        WHERE shift_id = ?
    """, (note, note, shift_id))

    conn.commit()
    return True

#is user available 
def get_checked_in_users(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT u.user_id, u.name, u.role, s.check_in_at
        FROM UserShift s
        JOIN User u ON u.user_id = s.user_id
        WHERE s.check_out_at IS NULL
          AND u.active = 1
        ORDER BY u.role, u.name
    """)
    return cur.fetchall()

#get mechanics list 
def get_mechanics(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, name, email, active
        FROM User 
        WHERE role = 'mechanic'
            AND active = 1
        ORDER BY name ASC
    """)
    return cur.fetchall()

def get_user_by_id(conn, user_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT
            user_id,
            name,
            role,
            email,
            active
        FROM User
        WHERE user_id = ?
    """, (user_id,))

    return cur.fetchone()