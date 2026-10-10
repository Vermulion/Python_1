"""Unit tests for AuditLog storage, levels, and filtration."""

import os
import tempfile
import unittest
from datetime import datetime

from audit_log import AuditLog, LogLevel


class AuditLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 6, 15, 12, 0)
        self.log = AuditLog(clock=lambda: self.now)

    def test_records_levels_in_memory(self) -> None:
        self.log.debug("trace", source="test")
        self.log.info("opened account", client_id="CL-1")
        self.log.warning("suspicious", account_id="ACC-1")
        self.log.error("failed", transaction_id="T1")
        self.log.critical("blocked", transaction_id="T2")
        self.assertEqual(len(self.log.entries()), 5)
        self.assertEqual(
            [entry.level for entry in self.log.entries()],
            [
                LogLevel.DEBUG,
                LogLevel.INFO,
                LogLevel.WARNING,
                LogLevel.ERROR,
                LogLevel.CRITICAL,
            ],
        )

    def test_filter_by_level_source_and_ids(self) -> None:
        self.log.info("a", source="bank", client_id="CL-1", account_id="A1")
        self.log.warning("b", source="risk", client_id="CL-1", transaction_id="T1")
        self.log.error("c", source="processor", client_id="CL-2", transaction_id="T2")
        self.assertEqual(len(self.log.filter(level="WARNING")), 1)
        self.assertEqual(len(self.log.filter(min_level="ERROR")), 1)
        self.assertEqual(len(self.log.filter(client_id="CL-1")), 2)
        self.assertEqual(len(self.log.filter(source="processor")), 1)
        self.assertEqual(len(self.log.filter(transaction_id="T1")), 1)

    def test_save_and_load_file(self) -> None:
        self.log.info("hello", source="bank", extra={"ok": True})
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "audit.jsonl")
            self.log.save(path)
            restored = AuditLog()
            restored.load(path)
            self.assertEqual(len(restored.entries()), 1)
            entry = restored.entries()[0]
            self.assertEqual(entry.message, "hello")
            self.assertEqual(entry.level, LogLevel.INFO)
            self.assertEqual(entry.extra["ok"], True)

    def test_auto_save_appends_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "audit.jsonl")
            log = AuditLog(filepath=path, auto_save=True, clock=lambda: self.now)
            log.info("one")
            log.warning("two")
            restored = AuditLog()
            restored.load(path)
            self.assertEqual([entry.message for entry in restored.entries()], ["one", "two"])


if __name__ == "__main__":
    unittest.main()
