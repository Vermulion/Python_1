"""Audit trail with importance levels, in-memory/file storage, and filters."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable
from uuid import uuid4


class LogLevel(Enum):
    """Importance of an audit record. Higher numeric value is more severe."""

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


def _resolve_level(level: LogLevel | str) -> LogLevel:
    if isinstance(level, LogLevel):
        return level
    key = str(level).strip().upper()
    try:
        return LogLevel[key]
    except KeyError as error:
        allowed = ", ".join(item.name for item in LogLevel)
        raise ValueError(f"unknown log level: {level}; use {allowed}") from error


@dataclass
class AuditEntry:
    """One audit record stored in memory and optionally on disk."""

    timestamp: datetime
    level: LogLevel
    message: str
    source: str = ""
    client_id: str | None = None
    account_id: str | None = None
    transaction_id: str | None = None
    extra: dict[str, object] = field(default_factory=dict)
    entry_id: str = field(default_factory=lambda: uuid4().hex[:8])

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        payload["level"] = self.level.name
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> AuditEntry:
        payload = dict(data)
        payload["timestamp"] = datetime.fromisoformat(str(payload["timestamp"]))
        payload["level"] = _resolve_level(str(payload["level"]))
        extra = payload.get("extra") or {}
        payload["extra"] = dict(extra) if isinstance(extra, dict) else {}
        return cls(**payload)  # type: ignore[arg-type]

    def __str__(self) -> str:
        who = self.client_id or self.account_id or "-"
        tx = f" tx={self.transaction_id}" if self.transaction_id else ""
        return (
            f"{self.timestamp.isoformat()} [{self.level.name}] "
            f"{self.source or 'audit'} {who}{tx}: {self.message}"
        )



class AuditLog:
    """In-memory audit log that can persist to a JSON-lines file."""

    def __init__(
        self,
        *,
        filepath: str | None = None,
        auto_save: bool = False,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.filepath = filepath
        self.auto_save = auto_save
        self._clock = clock or datetime.now
        self._entries: list[AuditEntry] = []

    def log(
        self,
        level: LogLevel | str,
        message: str,
        *,
        source: str = "",
        client_id: str | None = None,
        account_id: str | None = None,
        transaction_id: str | None = None,
        extra: dict[str, object] | None = None,
        timestamp: datetime | None = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            timestamp=timestamp or self._clock(),
            level=_resolve_level(level),
            message=str(message),
            source=str(source),
            client_id=client_id,
            account_id=account_id,
            transaction_id=transaction_id,
            extra=dict(extra or {}),
        )
        self._entries.append(entry)
        if self.filepath and self.auto_save:
            self._append_file(entry)
        return entry

    def debug(self, message: str, **kwargs: object) -> AuditEntry:
        return self.log(LogLevel.DEBUG, message, **kwargs)  # type: ignore[arg-type]

    def info(self, message: str, **kwargs: object) -> AuditEntry:
        return self.log(LogLevel.INFO, message, **kwargs)  # type: ignore[arg-type]

    def warning(self, message: str, **kwargs: object) -> AuditEntry:
        return self.log(LogLevel.WARNING, message, **kwargs)  # type: ignore[arg-type]

    def error(self, message: str, **kwargs: object) -> AuditEntry:
        return self.log(LogLevel.ERROR, message, **kwargs)  # type: ignore[arg-type]

    def critical(self, message: str, **kwargs: object) -> AuditEntry:
        return self.log(LogLevel.CRITICAL, message, **kwargs)  # type: ignore[arg-type]

    def entries(self) -> list[AuditEntry]:
        return list(self._entries)


    def filter(
        self,
        *,
        level: LogLevel | str | None = None,
        min_level: LogLevel | str | None = None,
        source: str | None = None,
        client_id: str | None = None,
        account_id: str | None = None,
        transaction_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[AuditEntry]:
        """Return records matching all provided conditions."""
        wanted_level = _resolve_level(level) if level is not None else None
        wanted_min = _resolve_level(min_level) if min_level is not None else None
        found: list[AuditEntry] = []
        for entry in self._entries:
            if wanted_level is not None and entry.level is not wanted_level:
                continue
            if wanted_min is not None and entry.level.value < wanted_min.value:
                continue
            if source is not None and entry.source != source:
                continue
            if client_id is not None and entry.client_id != client_id:
                continue
            if account_id is not None and entry.account_id != account_id:
                continue
            if transaction_id is not None and entry.transaction_id != transaction_id:
                continue
            if since is not None and entry.timestamp < since:
                continue
            if until is not None and entry.timestamp > until:
                continue
            found.append(entry)
        return found

    def save(self, path: str | None = None) -> str:
        """Write the in-memory log to a JSON-lines file."""
        target = path or self.filepath
        if not target:
            raise ValueError("audit log path is not set")
        with open(target, "w", encoding="utf-8") as handle:
            for entry in self._entries:
                handle.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        self.filepath = target
        return target

    def load(self, path: str | None = None) -> list[AuditEntry]:
        """Replace in-memory records with those stored in a JSON-lines file."""
        target = path or self.filepath
        if not target:
            raise ValueError("audit log path is not set")
        loaded: list[AuditEntry] = []
        with open(target, encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                loaded.append(AuditEntry.from_dict(json.loads(text)))
        self._entries = loaded
        self.filepath = target
        return self.entries()

    def _append_file(self, entry: AuditEntry) -> None:
        if not self.filepath:
            return
        with open(self.filepath, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

