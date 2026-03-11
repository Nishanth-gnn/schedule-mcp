from fastmcp import FastMCP
import os
import aiosqlite
from datetime import datetime
import json

# MCP Server
mcp = FastMCP("ScheduleServer")

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Data folder
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Users file
USERS_FILE = os.path.join(BASE_DIR, "users.json")


# -------- Authentication --------

def get_user_from_api_key(api_key: str):
    """Map API key to user_id"""
    try:
        with open(USERS_FILE, "r") as f:
            users = json.load(f)

        if api_key in users:
            return users[api_key]

        raise ValueError("Invalid API key")

    except Exception as e:
        raise ValueError(f"Authentication failed: {str(e)}")


# -------- Utility --------

def get_today():
    """Return today's date"""
    return datetime.now().strftime("%Y-%m-%d")


def get_user_db(user_id: str):
    """Return database path for a specific user"""
    return os.path.join(DATA_DIR, f"{user_id}.db")


async def init_user_db(user_id: str):
    """Create user schedule table if not exists"""
    db_path = get_user_db(user_id)

    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")

        await db.execute("""
        CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name TEXT NOT NULL,
            task_date TEXT NOT NULL,
            task_time TEXT,
            note TEXT
        )
        """)

        await db.commit()


# -------- MCP Tools --------

@mcp.tool()
async def today():
    """Returns today's date."""
    return {"today": get_today()}


@mcp.tool()
async def add_task(api_key: str, task_name: str, task_date: str, task_time: str = "", note: str = ""):
    """
    Add a task to the authenticated user's schedule.
    """

    user_id = get_user_from_api_key(api_key)

    await init_user_db(user_id)
    db_path = get_user_db(user_id)

    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")

        cursor = await db.execute(
            """
            INSERT INTO tasks(task_name, task_date, task_time, note)
            VALUES (?, ?, ?, ?)
            """,
            (task_name, task_date, task_time, note)
        )

        task_id = cursor.lastrowid
        await db.commit()

        return {
            "status": "success",
            "task_id": task_id,
            "message": "Task added successfully"
        }


@mcp.tool()
async def list_tasks(api_key: str, start_date: str, end_date: str):
    """
    List tasks for the authenticated user between two dates.
    """

    user_id = get_user_from_api_key(api_key)

    await init_user_db(user_id)
    db_path = get_user_db(user_id)

    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")

        cursor = await db.execute(
            """
            SELECT id, task_name, task_date, task_time, note
            FROM tasks
            WHERE task_date BETWEEN ? AND ?
            ORDER BY task_date ASC, task_time ASC
            """,
            (start_date, end_date)
        )

        rows = await cursor.fetchall()
        cols = [d[0] for d in cursor.description]

        return [dict(zip(cols, r)) for r in rows]


@mcp.tool()
async def delete_task(api_key: str, task_id: int):
    """
    Delete a task for the authenticated user.
    """

    user_id = get_user_from_api_key(api_key)

    await init_user_db(user_id)
    db_path = get_user_db(user_id)

    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")

        await db.execute(
            "DELETE FROM tasks WHERE id = ?",
            (task_id,)
        )

        await db.commit()

        return {
            "status": "success",
            "message": f"Task {task_id} deleted"
        }


@mcp.tool()
async def update_task(
    api_key: str,
    task_id: int,
    task_name: str = None,
    task_date: str = None,
    task_time: str = None,
    note: str = None
):
    """
    Update a task for the authenticated user.
    """

    user_id = get_user_from_api_key(api_key)

    await init_user_db(user_id)
    db_path = get_user_db(user_id)

    fields = []
    values = []

    if task_name is not None:
        fields.append("task_name = ?")
        values.append(task_name)

    if task_date is not None:
        fields.append("task_date = ?")
        values.append(task_date)

    if task_time is not None:
        fields.append("task_time = ?")
        values.append(task_time)

    if note is not None:
        fields.append("note = ?")
        values.append(note)

    if not fields:
        return {"status": "error", "message": "No updates provided"}

    values.append(task_id)

    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")

        await db.execute(
            f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?",
            values
        )

        await db.commit()

        return {
            "status": "success",
            "message": f"Task {task_id} updated"
        }


# -------- Server start --------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))

    mcp.run(
    transport="http",
    host="0.0.0.0",
    port=port,
    path="/mcp"
)
