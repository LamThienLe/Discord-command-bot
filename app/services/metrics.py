from __future__ import annotations

import time
import asyncio
from typing import Dict, Any, Optional
from collections import defaultdict, Counter
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


@dataclass
class CommandMetrics:
    total_calls: int = 0
    success_calls: int = 0
    error_calls: int = 0
    total_duration: float = 0.0
    avg_duration: float = 0.0
    last_called: Optional[datetime] = None
    error_types: Counter[str] = field(default_factory=Counter)


@dataclass
class UserMetrics:
    total_commands: int = 0
    commands_by_type: Counter[str] = field(default_factory=Counter)
    last_active: Optional[datetime] = None
    timezone: Optional[str] = None


class MetricsCollector:
    def __init__(self) -> None:
        self.command_metrics: Dict[str, CommandMetrics] = defaultdict(CommandMetrics)
        self.user_metrics: Dict[int, UserMetrics] = defaultdict(UserMetrics)
        self.start_time = datetime.now()
        self._lock = asyncio.Lock()

    async def record_command_start(self, command: str, user_id: int) -> float:
        """Record command start and return start time."""
        start_time = time.time()
        async with self._lock:
            self.command_metrics[command].total_calls += 1
            self.command_metrics[command].last_called = datetime.now()
            
            self.user_metrics[user_id].total_commands += 1
            self.user_metrics[user_id].commands_by_type[command] += 1
            self.user_metrics[user_id].last_active = datetime.now()
        
        return start_time

    async def record_command_success(self, command: str, user_id: int, start_time: float) -> None:
        """Record successful command completion."""
        duration = time.time() - start_time
        async with self._lock:
            metrics = self.command_metrics[command]
            metrics.success_calls += 1
            metrics.total_duration += duration
            metrics.avg_duration = metrics.total_duration / metrics.success_calls

    async def record_command_error(self, command: str, user_id: int, start_time: float, error_type: str) -> None:
        """Record command error."""
        duration = time.time() - start_time
        async with self._lock:
            metrics = self.command_metrics[command]
            metrics.error_calls += 1
            metrics.error_types[error_type] += 1
            metrics.total_duration += duration
            if metrics.success_calls > 0:
                metrics.avg_duration = metrics.total_duration / metrics.success_calls

    async def record_user_timezone(self, user_id: int, timezone: str) -> None:
        """Record user timezone preference."""
        async with self._lock:
            self.user_metrics[user_id].timezone = timezone

    async def get_command_stats(self, command: Optional[str] = None) -> Dict[str, Any]:
        """Get command statistics."""
        async with self._lock:
            if command:
                metrics = self.command_metrics.get(command)
                if not metrics:
                    return {}
                return {
                    "total_calls": metrics.total_calls,
                    "success_rate": metrics.success_calls / metrics.total_calls if metrics.total_calls > 0 else 0,
                    "avg_duration": metrics.avg_duration,
                    "last_called": metrics.last_called.isoformat() if metrics.last_called else None,
                    "error_types": dict(metrics.error_types)
                }
            else:
                return {
                    cmd: {
                        "total_calls": metrics.total_calls,
                        "success_rate": metrics.success_calls / metrics.total_calls if metrics.total_calls > 0 else 0,
                        "avg_duration": metrics.avg_duration
                    }
                    for cmd, metrics in self.command_metrics.items()
                }

    async def get_user_stats(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get user statistics."""
        async with self._lock:
            if user_id:
                metrics = self.user_metrics.get(user_id)
                if not metrics:
                    return {}
                return {
                    "total_commands": metrics.total_commands,
                    "commands_by_type": dict(metrics.commands_by_type),
                    "last_active": metrics.last_active.isoformat() if metrics.last_active else None,
                    "timezone": metrics.timezone
                }
            else:
                return {
                    "total_users": len(self.user_metrics),
                    "active_users_24h": len([
                        u for u in self.user_metrics.values() 
                        if u.last_active and u.last_active > datetime.now() - timedelta(days=1)
                    ]),
                    "top_commands": dict(Counter().update(
                        cmd for user in self.user_metrics.values() 
                        for cmd, count in user.commands_by_type.items()
                        for _ in range(count)
                    ).most_common(5))
                }

    async def get_system_stats(self) -> Dict[str, Any]:
        """Get overall system statistics."""
        async with self._lock:
            uptime = datetime.now() - self.start_time
            total_commands = sum(m.total_calls for m in self.command_metrics.values())
            total_errors = sum(m.error_calls for m in self.command_metrics.values())
            
            return {
                "uptime_seconds": uptime.total_seconds(),
                "total_commands": total_commands,
                "total_errors": total_errors,
                "error_rate": total_errors / total_commands if total_commands > 0 else 0,
                "commands_per_minute": total_commands / (uptime.total_seconds() / 60) if uptime.total_seconds() > 0 else 0
            }

    async def export_metrics(self) -> Dict[str, Any]:
        """Export all metrics for external monitoring."""
        return {
            "system": await self.get_system_stats(),
            "commands": await self.get_command_stats(),
            "users": await self.get_user_stats(),
            "timestamp": datetime.now().isoformat()
        }


# Global metrics collector
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    return _metrics_collector


async def metrics_middleware(command: str, user_id: int, func, *args, **kwargs):
    """Middleware to automatically collect metrics for commands."""
    start_time = await _metrics_collector.record_command_start(command, user_id)
    
    try:
        result = await func(*args, **kwargs)
        await _metrics_collector.record_command_success(command, user_id, start_time)
        return result
    except Exception as e:
        error_type = type(e).__name__
        await _metrics_collector.record_command_error(command, user_id, start_time, error_type)
        raise
