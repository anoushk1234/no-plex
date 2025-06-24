import requests
import sqlite3
from datetime import datetime, timezone, time as dtime
import os

KILL_MESSAGE = os.getenv(
    "KILL_MESSAGE",
    "HOOOLY JESUS! WHAT IS THAT?! WHAT THE FUCK IS THAT?! WHAT IS THAT PRIVATE PYLE?",
)
TAUTULLI_URL = os.getenv("TAUTULLI_URL", "http://127.0.0.1:8181")
API_KEY = os.getenv("TAUTULLI_API_KEY", "")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "plex_session_tracker.db")
LOG_FILE = os.path.join(SCRIPT_DIR, "plex_session_tracker.log")

MAX_SESSION_DURATION_MINUTES = os.getenv("MAX_SESSION_DURATION_MINUTES", 30)
MAX_TOTAL_MINUTES = os.getenv("MAX_TOTAL_MINUTES", 60)
ENABLE_BEDTIME = os.getenv("ENABLE_BEDTIME", 0)
PAUSE_THRESHOLD = os.getenv(
    "PAUSE_THRESHOLD", 120
)  # Since tautulli api doesnt tell us if user closed stream before time, this is a timeout.


def log(message):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} - {message}\n")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS session_tracker (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            user_id TEXT,
            username TEXT,
            rating_key TEXT,
            start_time TEXT,
            duration_minutes REAL DEFAULT 0,
            is_terminated INTEGER NOT NULL DEFAULT 0,
            is_saturated INTEGER NOT NULL DEFAULT 0
        )
    """
    )
    conn.commit()
    conn.close()


def cleanup_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM session_tracker")
    conn.commit()
    conn.close()
    log("Database cleaned at 23:59")


def get_or_create_active_segment(session_id, user_id, username, rating_key):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, start_time FROM session_tracker
        WHERE session_id = ? AND user_id = ? AND is_terminated = 0 AND is_saturated = 0;
    """,
        (session_id, user_id),
    )
    row = cur.fetchone()
    # AND duration_minutes = 0
    if row:
        segment_id, start_time = row
        time_gap = (
            datetime.now(timezone.utc) - datetime.fromisoformat(start_time)
        ).total_seconds()
        if time_gap > PAUSE_THRESHOLD:
            mark_segment_saturated(segment_id)
            # mark_segment_terminated(segment_id) not doing this since we chain all them and then terminate
            start_time = datetime.now(timezone.utc).isoformat()
            cur.execute(
                """
                INSERT INTO session_tracker (session_id, user_id, username, rating_key, start_time)
                VALUES (?, ?, ?, ?, ?)
            """,
                (session_id, user_id, username, rating_key, start_time),
            )
            segment_id = cur.lastrowid
    else:
        start_time = datetime.now(timezone.utc).isoformat()
        cur.execute(
            """
            INSERT INTO session_tracker (session_id, user_id, username, rating_key, start_time)
            VALUES (?, ?, ?, ?, ?)
        """,
            (session_id, user_id, username, rating_key, start_time),
        )
        segment_id = cur.lastrowid

    conn.commit()
    conn.close()
    return segment_id, datetime.fromisoformat(start_time).replace(tzinfo=timezone.utc)


def update_segment_duration(segment_id, duration):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "UPDATE session_tracker SET duration_minutes = ? WHERE id = ?",
        (duration, segment_id),
    )
    conn.commit()
    conn.close()


def mark_segment_terminated(segment_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE session_tracker
        SET is_terminated = 1
        WHERE id = ?
    """,
        (segment_id,),
    )
    conn.commit()
    conn.close()


def mark_session_terminated(session_id, user_id, rating_key):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE session_tracker
        SET is_terminated = 1
        WHERE session_id = ?
         AND user_id = ?
         AND rating_key = ?
    """,
        (session_id, user_id, rating_key),
    )
    conn.commit()
    conn.close()


def mark_segment_saturated(segment_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE session_tracker
        SET is_saturated = 1
        WHERE id = ?
    """,
        (segment_id,),
    )
    conn.commit()
    conn.close()


def get_total_watch_time_today_from_db(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    cur.execute(
        """
        SELECT SUM(duration_minutes)
        FROM session_tracker
        WHERE user_id = ? AND DATE(start_time) = ? AND is_terminated = 1
    """,
        (user_id, today),
    )
    row = cur.fetchone()
    conn.close()
    return row[0] or 0


def get_active_sessions():
    try:
        r = requests.get(f"{TAUTULLI_URL}/api/v2?apikey={API_KEY}&cmd=get_activity")
        return r.json()["response"]["data"].get("sessions", [])
    except Exception as e:
        log(f"[ERROR] Failed to fetch sessions: {e}")
        return []


def get_total_unterminated_duration(session_id, user_id, rating_key):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT SUM(duration_minutes)
        FROM session_tracker
        WHERE user_id = ?
          AND is_saturated = 1
          AND is_terminated = 0
    """,
        (user_id, ),
    )
    row = cur.fetchone()
    conn.close()
    # log(f"[INFO] {row} {session_id} {user_id} {rating_key}")
    return row[0] if row and row[0] else 0.0


def is_blocked_time():
    now = datetime.now().time()
    return now >= dtime(22, 30) or now < dtime(13, 0)


def is_sunday():
    return datetime.today().weekday() == 6  # Sunday is 6


def terminate_session(session_id, reason):
    log(f"[TERMINATE] {session_id}: {reason}")
    requests.get(
        f"{TAUTULLI_URL}/api/v2",
        params={
            "apikey": API_KEY,
            "cmd": "terminate_session",
            "session_id": session_id,
            "message": reason,
        },
    )


def main():
    init_db()
    now = datetime.now()

    if now.hour == 23 and now.minute == 59:
        cleanup_db()
        return
    # Disable if needed
    if is_sunday():
        return

    sessions = get_active_sessions()
    for session in sessions:
        session_id = session["session_id"]
        user_id = session["user_id"]
        username = session["username"]
        rating_key = session["rating_key"]
        state = session["state"]  # playing

        if ENABLE_BEDTIME and is_blocked_time():
            terminate_session(
                session_id, f"Blocked hours (10:30 PM – 1:00 PM). {KILL_MESSAGE}"
            )
            continue
        if state and state != "playing":
            continue

        segment_id, start_time = get_or_create_active_segment(
            session_id, user_id, username, rating_key
        )
        sub_session_duration = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds() / 60

        terminated_stream_dur_today = get_total_watch_time_today_from_db(user_id)

        update_segment_duration(segment_id, sub_session_duration)
        sum_session_duration = get_total_unterminated_duration(
            session_id, user_id, rating_key
        )
        total_today = (
            terminated_stream_dur_today + sum_session_duration + sub_session_duration
        )
        log(
            f"[INFO] termd_today: {terminated_stream_dur_today:.2f}, Sum_sesh: {sum_session_duration:.2f} min, Sub_sesh: {sub_session_duration:.2f} min, Total today: {total_today:.2f} min"
        )
        log(total_today > MAX_TOTAL_MINUTES)
        if total_today > MAX_TOTAL_MINUTES:
            mark_session_terminated(session_id, user_id, rating_key)
            terminate_session(
                session_id,
                f"You've hit your daily limit of {MAX_TOTAL_MINUTES} minutes. {KILL_MESSAGE}",
            )
        elif sum_session_duration > MAX_SESSION_DURATION_MINUTES:
            mark_session_terminated(session_id, user_id, rating_key)
            terminate_session(
                session_id,
                f"Session exceeded {MAX_SESSION_DURATION_MINUTES} minutes. {KILL_MESSAGE}",
            )


if __name__ == "__main__":
    main()
