import sqlite3

def setup_defaults(db_path: str):
    print(f"Configuring defaults for {db_path}...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Ensure min_afternoon_off column
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(teachers)")}
    if "min_afternoon_off" not in cols:
        conn.execute("ALTER TABLE teachers ADD COLUMN min_afternoon_off INTEGER")
        conn.commit()

    # 1. GV Hồng: min_afternoon_off = 2
    conn.execute("UPDATE teachers SET min_afternoon_off = 2 WHERE name LIKE '%Hồng%'")
    conn.commit()

    # 2. GV Hà: busy all except T3-4 mornings period 2-3
    ha_row = conn.execute("SELECT teacher_id, name FROM teachers WHERE name LIKE '%Hà%'").fetchone()
    if ha_row:
        ha_id = ha_row["teacher_id"]
        # Clear existing unavail
        conn.execute("DELETE FROM teacher_unavailability WHERE teacher_id = ?", (ha_id,))
        # All slots: weekdays 2..7, session S & C, period 1..5
        all_cells = {(w, s, p) for w in range(2, 8) for s in ("S", "C") for p in range(1, 6)}
        open_cells = {(3, "S", 2), (3, "S", 3), (4, "S", 2), (4, "S", 3)}
        busy_cells = all_cells - open_cells
        for w, s, p in sorted(busy_cells):
            conn.execute(
                "INSERT INTO teacher_unavailability (teacher_id, weekday, session, period) VALUES (?, ?, ?, ?)",
                (ha_id, str(w), s, p)
            )
        conn.commit()
        print(f"GV Hà (ID {ha_id}): inserted {len(busy_cells)} busy cells, open 4 cells.")

    # 3. Period frames: K67 = 29 periods, K89 = 30 periods
    # Frame templates / class allowed cells
    classes = conn.execute("SELECT class_id, name FROM classes").fetchall()
    k67 = [c for c in classes if c["name"].startswith(('6', '7'))]
    k89 = [c for c in classes if c["name"].startswith(('8', '9'))]
    print(f"Classes: K67 count = {len(k67)}, K89 count = {len(k89)}")

    # For K67: Saturday (weekday 7) period 5 is off -> 29 periods
    # For K89: 30 periods -> all 6 days x 5 morning periods = 30 periods
    # Let's inspect class_unavailability / class allowed cells table if any
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    print("Tables in DB:", sorted(tables))

    # 3. Check and set app_meta
    rows = conn.execute("SELECT key, value FROM app_meta WHERE key IN ('forbidden_off_cells', 'mandatory_morning_weekdays')").fetchall()
    print("app_meta before:", [dict(r) for r in rows])
    # Set forbidden_off_cells to '2S'
    conn.execute("INSERT INTO app_meta (key, value) VALUES ('forbidden_off_cells', '2S') ON CONFLICT(key) DO UPDATE SET value='2S'")
    # Set mandatory_morning_weekdays to '2'
    conn.execute("INSERT INTO app_meta (key, value) VALUES ('mandatory_morning_weekdays', '2') ON CONFLICT(key) DO UPDATE SET value='2'")
    conn.commit()

    # 4. Period frames: K67 = 29 periods, K89 = 30 periods
    # Check class_allowed_cells
    # For K67: Saturday (wd 7) period 5 is disallowed (or not allowed)
    classes = conn.execute("SELECT class_id, name FROM classes").fetchall()
    k67 = [c for c in classes if c["name"].startswith(('6', '7'))]
    k89 = [c for c in classes if c["name"].startswith(('8', '9'))]
    print(f"Classes: K67 count = {len(k67)}, K89 count = {len(k89)}")

    # For K67, ensure Saturday period 5 is deleted from class_allowed_cells if present
    for c in k67:
        cid = c["class_id"]
        # Delete Saturday period 5
        conn.execute("DELETE FROM class_allowed_cells WHERE class_id = ? AND weekday = '7' AND session = 'S' AND period = 5", (cid,))
        # Ensure Monday-Friday (all 5 periods) and Saturday periods 1-4 are present
        for w in range(2, 7):
            for p in range(1, 6):
                conn.execute("INSERT OR IGNORE INTO class_allowed_cells (class_id, weekday, session, period) VALUES (?, ?, 'S', ?)", (cid, str(w), p))
        for p in range(1, 5):
            conn.execute("INSERT OR IGNORE INTO class_allowed_cells (class_id, weekday, session, period) VALUES (?, '7', 'S', ?)", (cid, p))

    # For K89, ensure all 30 periods (Monday-Saturday, periods 1-5) are present
    for c in k89:
        cid = c["class_id"]
        for w in range(2, 8):
            for p in range(1, 6):
                conn.execute("INSERT OR IGNORE INTO class_allowed_cells (class_id, weekday, session, period) VALUES (?, ?, 'S', ?)", (cid, str(w), p))

    conn.commit()
    conn.close()
    print(f"Finished defaults for {db_path}\n")

if __name__ == "__main__":
    setup_defaults("schools/truong-thcs.db")
    setup_defaults("schools/truong-thcs-2-buoi.db")
