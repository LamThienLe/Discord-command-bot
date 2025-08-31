from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
import sqlite3
import os
from pathlib import Path


logger = logging.getLogger(__name__)


@dataclass
class Task:
    id: Optional[int]
    user_id: int
    title: str
    description: Optional[str]
    due_date: Optional[dt.datetime]
    priority: str  # "low", "medium", "high", "urgent"
    status: str  # "pending", "in_progress", "completed", "cancelled"
    created_at: dt.datetime
    updated_at: dt.datetime
    tags: List[str]
    reminder_sent: bool = False


class TaskManager:
    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / "tasks.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    due_date TEXT,
                    priority TEXT NOT NULL DEFAULT 'medium',
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    tags TEXT,
                    reminder_sent BOOLEAN DEFAULT FALSE
                )
            """)
            conn.commit()

    def _datetime_to_iso(self, dt_obj: Optional[dt.datetime]) -> Optional[str]:
        """Convert datetime to ISO string for storage."""
        return dt_obj.isoformat() if dt_obj else None

    def _iso_to_datetime(self, iso_str: Optional[str]) -> Optional[dt.datetime]:
        """Convert ISO string to datetime."""
        if not iso_str:
            return None
        try:
            return dt.datetime.fromisoformat(iso_str)
        except ValueError:
            return None

    def _task_from_row(self, row: tuple) -> Task:
        """Create Task object from database row."""
        return Task(
            id=row[0],
            user_id=row[1],
            title=row[2],
            description=row[3],
            due_date=self._iso_to_datetime(row[4]),
            priority=row[5],
            status=row[6],
            created_at=self._iso_to_datetime(row[7]) or dt.datetime.now(),
            updated_at=self._iso_to_datetime(row[8]) or dt.datetime.now(),
            tags=json.loads(row[9]) if row[9] else [],
            reminder_sent=bool(row[10])
        )

    def create_task(
        self,
        user_id: int,
        title: str,
        description: Optional[str] = None,
        due_date: Optional[dt.datetime] = None,
        priority: str = "medium",
        tags: Optional[List[str]] = None
    ) -> Task:
        """Create a new task."""
        now = dt.datetime.now()
        task = Task(
            id=None,
            user_id=user_id,
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
            status="pending",
            created_at=now,
            updated_at=now,
            tags=tags or []
        )

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO tasks (user_id, title, description, due_date, priority, status, created_at, updated_at, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.user_id,
                task.title,
                task.description,
                self._datetime_to_iso(task.due_date),
                task.priority,
                task.status,
                self._datetime_to_iso(task.created_at),
                self._datetime_to_iso(task.updated_at),
                json.dumps(task.tags)
            ))
            task.id = cursor.lastrowid

        logger.info(f"Created task {task.id} for user {user_id}: {title}")
        return task

    def get_task(self, task_id: int, user_id: int) -> Optional[Task]:
        """Get a specific task by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM tasks WHERE id = ? AND user_id = ?
            """, (task_id, user_id))
            row = cursor.fetchone()
            return self._task_from_row(row) if row else None

    def get_user_tasks(
        self,
        user_id: int,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        include_completed: bool = True
    ) -> List[Task]:
        """Get tasks for a user with optional filters."""
        query = "SELECT * FROM tasks WHERE user_id = ?"
        params = [user_id]

        if status:
            query += " AND status = ?"
            params.append(status)
        elif not include_completed:
            query += " AND status != 'completed'"

        if priority:
            query += " AND priority = ?"
            params.append(priority)

        query += " ORDER BY due_date ASC, priority DESC, created_at DESC"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            return [self._task_from_row(row) for row in cursor.fetchall()]

    def update_task(
        self,
        task_id: int,
        user_id: int,
        **updates: Any
    ) -> Optional[Task]:
        """Update a task."""
        allowed_fields = {
            'title', 'description', 'due_date', 'priority', 'status', 'tags'
        }
        
        update_fields = {k: v for k, v in updates.items() if k in allowed_fields}
        if not update_fields:
            return None

        update_fields['updated_at'] = dt.datetime.now()
        
        # Convert datetime fields
        if 'due_date' in update_fields and isinstance(update_fields['due_date'], dt.datetime):
            update_fields['due_date'] = self._datetime_to_iso(update_fields['due_date'])
        
        if 'tags' in update_fields:
            update_fields['tags'] = json.dumps(update_fields['tags'])

        set_clause = ", ".join(f"{k} = ?" for k in update_fields.keys())
        values = list(update_fields.values()) + [task_id, user_id]

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"""
                UPDATE tasks SET {set_clause}
                WHERE id = ? AND user_id = ?
            """, values)
            conn.commit()

        logger.info(f"Updated task {task_id} for user {user_id}")
        return self.get_task(task_id, user_id)

    def delete_task(self, task_id: int, user_id: int) -> bool:
        """Delete a task."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM tasks WHERE id = ? AND user_id = ?
            """, (task_id, user_id))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted task {task_id} for user {user_id}")
            return deleted

    def get_overdue_tasks(self, user_id: int) -> List[Task]:
        """Get overdue tasks for a user."""
        now = dt.datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM tasks 
                WHERE user_id = ? AND due_date < ? AND status = 'pending'
                ORDER BY due_date ASC
            """, (user_id, self._datetime_to_iso(now)))
            return [self._task_from_row(row) for row in cursor.fetchall()]

    def get_due_soon_tasks(self, user_id: int, hours: int = 24) -> List[Task]:
        """Get tasks due within the next N hours."""
        now = dt.datetime.now()
        future = now + dt.timedelta(hours=hours)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM tasks 
                WHERE user_id = ? AND due_date BETWEEN ? AND ? AND status = 'pending'
                ORDER BY due_date ASC
            """, (user_id, self._datetime_to_iso(now), self._datetime_to_iso(future)))
            return [self._task_from_row(row) for row in cursor.fetchall()]

    def mark_reminder_sent(self, task_id: int, user_id: int) -> None:
        """Mark that a reminder has been sent for a task."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE tasks SET reminder_sent = TRUE
                WHERE id = ? AND user_id = ?
            """, (task_id, user_id))
            conn.commit()

    def get_task_summary(self, user_id: int) -> Dict[str, Any]:
        """Get a summary of user's tasks."""
        with sqlite3.connect(self.db_path) as conn:
            # Total tasks by status
            cursor = conn.execute("""
                SELECT status, COUNT(*) FROM tasks 
                WHERE user_id = ? GROUP BY status
            """, (user_id,))
            status_counts = dict(cursor.fetchall())

            # Total tasks by priority
            cursor = conn.execute("""
                SELECT priority, COUNT(*) FROM tasks 
                WHERE user_id = ? AND status != 'completed' GROUP BY priority
            """, (user_id,))
            priority_counts = dict(cursor.fetchall())

            # Overdue tasks count
            cursor = conn.execute("""
                SELECT COUNT(*) FROM tasks 
                WHERE user_id = ? AND due_date < ? AND status = 'pending'
            """, (user_id, self._datetime_to_iso(dt.datetime.now())))
            overdue_count = cursor.fetchone()[0]

        return {
            "total_tasks": sum(status_counts.values()),
            "by_status": status_counts,
            "by_priority": priority_counts,
            "overdue": overdue_count
        }


# Global task manager instance
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager


def create_task_from_text(text: str, user_id: int, user_tz: str = "Asia/Ho_Chi_Minh") -> Task:
    """Create a task from natural language text."""
    from ..utils.timeparse import parse_times_and_summary
    
    # Extract time and summary from text
    start, end, summary = parse_times_and_summary(text, user_tz)
    
    # Determine priority based on keywords
    text_lower = text.lower()
    if any(word in text_lower for word in ["urgent", "asap", "emergency", "critical"]):
        priority = "urgent"
    elif any(word in text_lower for word in ["important", "high", "priority"]):
        priority = "high"
    elif any(word in text_lower for word in ["low", "whenever", "sometime"]):
        priority = "low"
    else:
        priority = "medium"
    
    # Extract tags (words starting with #)
    tags = [word[1:] for word in text.split() if word.startswith("#")]
    
    # Use start time as due date if available
    due_date = start if start else None
    
    # Create a better title if summary is empty or generic
    if not summary or summary.lower() in ["event", "meeting", "task"]:
        # Extract first meaningful words from the text
        words = text.split()
        # Remove common task words and time-related words
        filtered_words = []
        skip_words = {
            "task", "create", "add", "make", "schedule", "set", "remind", "me", "to",
            "tomorrow", "today", "next", "this", "at", "on", "by", "for", "in", "the",
            "a", "an", "and", "or", "but", "urgent", "important", "asap", "low", "high"
        }
        
        for word in words:
            clean_word = word.strip(".,!?").lower()
            if (clean_word not in skip_words and 
                not clean_word.startswith("#") and 
                not clean_word.isdigit() and
                len(clean_word) > 2):
                filtered_words.append(word)
        
        if filtered_words:
            # Take first 3-4 meaningful words
            title = " ".join(filtered_words[:4]).title()
        else:
            # Fallback: use first few words of original text
            title = " ".join(words[:3]).title()
    else:
        title = summary
    
    # Ensure title is not too long
    if len(title) > 100:
        title = title[:97] + "..."
    
    task_manager = get_task_manager()
    return task_manager.create_task(
        user_id=user_id,
        title=title,
        description=text,
        due_date=due_date,
        priority=priority,
        tags=tags
    )