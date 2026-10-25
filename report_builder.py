"""Build client, bank, and risk reports and export them with charts."""

from __future__ import annotations

import csv
import json
import os
from collections import Counter
from datetime import datetime
from typing import Any

from bank import Bank
from risk_analyzer import RiskLevel
from transaction import Transaction, TransactionProcessor, TransactionStatus


def _to_jsonable(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value") and not isinstance(value, (str, bytes, dict, list)):
        try:
            return value.value  # type: ignore[attr-defined]
        except Exception:
            return str(value)
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    return value


def _ensure_dir(path: str) -> str:
    directory = os.path.abspath(path)
    os.makedirs(directory, exist_ok=True)
    return directory


def _write_text(path: str, text: str) -> str:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return os.path.abspath(path)


class ReportBuilder:
    """Form TXT / JSON / CSV reports and matplotlib charts from bank data."""

    def __init__(
        self,
        bank: Bank,
        processor: TransactionProcessor | None = None,
        transactions: list[Transaction] | None = None,
        output_dir: str = "reports",
    ) -> None:
        if not isinstance(bank, Bank):
            raise TypeError("bank must be a Bank instance")
        self.bank = bank
        self.processor = processor
        if transactions is not None:
            self.transactions = list(transactions)
        elif processor is not None:
            self.transactions = list(processor.queue._items.values())
        else:
            self.transactions = []
        self.output_dir = output_dir

    def client_report(self, client_id: str) -> dict[str, Any]:
        client = self.bank._require_client(client_id)
        owned = {account.account_id for account in client.accounts}
        history = [
            self._transaction_row(tx)
            for tx in self._sorted_transactions()
            if tx.sender_id in owned or tx.receiver_id in owned
        ]
        risk = {}
        if self.processor is not None:
            risk = self.processor.reporter.client_risk_profile(client_id)
        return {
            "kind": "client",
            "generated_at": self._now().isoformat(),
            "client_id": client.client_id,
            "full_name": client.full_name,
            "status": client.status.value,
            "tags": list(client.tags),
            "total_balance_rub": self.bank.get_total_balance(client.client_id),
            "accounts": [self._account_row(account) for account in client.accounts],
            "transactions": history,
            "risk": risk,
        }

    def bank_report(self) -> dict[str, Any]:
        ranking = self.bank.get_clients_ranking()
        by_status = Counter(tx.status.value for tx in self.transactions)
        by_type = Counter(tx.tx_type.value for tx in self.transactions)
        completed = [
            tx for tx in self.transactions if tx.status is TransactionStatus.COMPLETED
        ]
        return {
            "kind": "bank",
            "generated_at": self._now().isoformat(),
            "bank_name": self.bank.name,
            "clients": len(self.bank._clients),
            "accounts": len(self.bank._accounts),
            "total_balance_rub": self.bank.get_total_balance(),
            "ranking": ranking,
            "transaction_statistics": {
                "total": len(self.transactions),
                "by_status": dict(by_status),
                "by_type": dict(by_type),
                "completed_volume": round(sum(tx.amount for tx in completed), 2),
                "completed_fees": round(sum(tx.transfer_fee for tx in completed), 2),
            },
            "transactions": [self._transaction_row(tx) for tx in self._sorted_transactions()],
        }

    def risk_report(self) -> dict[str, Any]:
        analyzer = self.processor.risk_analyzer if self.processor is not None else None
        reporter = self.processor.reporter if self.processor is not None else None
        assessments = []
        if analyzer is not None:
            for item in analyzer.assessments:
                assessments.append(
                    {
                        "transaction_id": item.transaction_id,
                        "client_id": item.client_id,
                        "sender_id": item.sender_id,
                        "receiver_id": item.receiver_id,
                        "risk_level": item.level.value,
                        "signals": list(item.signals),
                        "amount_rub": item.amount_rub,
                        "at": item.at.isoformat(),
                    }
                )
        by_level = Counter(row["risk_level"] for row in assessments)
        by_signal: Counter[str] = Counter()
        for row in assessments:
            by_signal.update(row["signals"])
        suspicious = reporter.suspicious_transactions() if reporter is not None else []
        errors = reporter.error_statistics() if reporter is not None else {}
        profiles = []
        if reporter is not None:
            for client_id in self.bank._clients:
                profiles.append(reporter.client_risk_profile(client_id))
        return {
            "kind": "risk",
            "generated_at": self._now().isoformat(),
            "by_level": {level.value: by_level.get(level.value, 0) for level in RiskLevel},
            "by_signal": dict(by_signal),
            "assessments": assessments,
            "suspicious": [
                {
                    **row,
                    "at": row["at"].isoformat()
                    if isinstance(row.get("at"), datetime)
                    else row.get("at"),
                    "signals": list(row.get("signals") or []),
                }
                for row in suspicious
            ],
            "client_profiles": profiles,
            "error_statistics": errors,
        }

    def to_txt(self, report: dict[str, Any]) -> str:
        kind = str(report.get("kind", "report")).upper()
        lines = [f"{kind} REPORT", "=" * 72]
        skip = {
            "transactions",
            "ranking",
            "accounts",
            "assessments",
            "suspicious",
            "client_profiles",
        }
        for key, value in report.items():
            if key in skip:
                continue
            if isinstance(value, dict):
                lines.append(f"{key}:")
                for inner_key, inner_value in value.items():
                    lines.append(f"  {inner_key}: {inner_value}")
            else:
                lines.append(f"{key}: {value}")
        table = self._tabular_rows(report)
        if table:
            lines.append("")
            lines.append("details:")
            headers = list(table[0].keys())
            lines.append("  " + " | ".join(headers))
            for row in table:
                lines.append(
                    "  " + " | ".join(str(row.get(header, "")) for header in headers)
                )
        return "\n".join(lines) + "\n"


    def export_to_txt(self, path: str, report: dict[str, Any] | None = None) -> str:
        payload = report if report is not None else self.bank_report()
        return _write_text(path, self.to_txt(payload))

    def export_to_json(self, path: str, report: dict[str, Any] | None = None) -> str:
        payload = report if report is not None else self.bank_report()
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(_to_jsonable(payload), handle, ensure_ascii=False, indent=2)
        return os.path.abspath(path)

    def export_to_csv(self, path: str, report: dict[str, Any] | None = None) -> str:
        payload = report if report is not None else self.bank_report()
        rows = self._tabular_rows(payload)
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        if not rows:
            rows = [
                {
                    "kind": payload.get("kind", ""),
                    "generated_at": payload.get("generated_at", ""),
                }
            ]
        fieldnames: list[str] = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: self._csv_cell(row.get(key)) for key in fieldnames})
        return os.path.abspath(path)

    def save_charts(self, directory: str | None = None) -> dict[str, str]:
        """Save pie, bar, and balance-movement charts as PNG files."""
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        target = _ensure_dir(directory or os.path.join(self.output_dir, "charts"))
        saved: dict[str, str] = {}
        status_counts = Counter(tx.status.value for tx in self.transactions)
        saved["pie_status"] = self._save_pie(
            plt,
            os.path.join(target, "pie_status.png"),
            status_counts,
            "Transactions by status",
        )
        risk_counts = Counter(
            item.level.value
            for item in (
                self.processor.risk_analyzer.assessments
                if self.processor is not None
                else []
            )
        )
        saved["pie_risk"] = self._save_pie(
            plt, os.path.join(target, "pie_risk.png"), risk_counts, "Risk levels"
        )
        ranking = self.bank.get_clients_ranking()
        saved["bar_balances"] = self._save_bar(
            plt,
            os.path.join(target, "bar_balances.png"),
            [str(row["full_name"]) for row in ranking],
            [float(row["total_balance"]) for row in ranking],
            "Client balances (RUB)",
            "RUB",
        )
        error_counts: Counter[str] = Counter()
        if self.processor is not None:
            for row in self.processor.error_log:
                error_counts[str(row.get("error", "unknown"))] += 1
        saved["bar_errors"] = self._save_bar(
            plt,
            os.path.join(target, "bar_errors.png"),
            list(error_counts.keys()) or ["none"],
            list(error_counts.values()) or [0],
            "Processor errors",
            "count",
        )
        saved["balance_movement"] = self._save_line(
            plt,
            os.path.join(target, "balance_movement.png"),
            self.balance_series(),
            "Bank balance movement (RUB)",
        )
        plt.close("all")
        return saved


    def export_all(self, directory: str | None = None) -> dict[str, str]:
        target = _ensure_dir(directory or self.output_dir)
        reports: dict[str, dict[str, Any]] = {
            "bank": self.bank_report(),
            "risk": self.risk_report(),
        }
        if self.bank._clients:
            first_id = next(iter(self.bank._clients))
            reports["client"] = self.client_report(first_id)
        paths: dict[str, str] = {}
        for kind, report in reports.items():
            paths[f"{kind}_json"] = self.export_to_json(
                os.path.join(target, f"{kind}_report.json"), report
            )
            paths[f"{kind}_csv"] = self.export_to_csv(
                os.path.join(target, f"{kind}_report.csv"), report
            )
            paths[f"{kind}_txt"] = self.export_to_txt(
                os.path.join(target, f"{kind}_report.txt"), report
            )
        paths.update(self.save_charts(os.path.join(target, "charts")))
        return paths

    def balance_series(
        self, client_id: str | None = None
    ) -> list[tuple[datetime, float]]:
        """Approximate balance over time from completed transfers (RUB)."""
        current = self.bank.get_total_balance(client_id)
        owned: set[str] | None = None
        if client_id is not None:
            owned = {
                account.account_id
                for account in self.bank._require_client(client_id).accounts
            }
        completed = [
            tx
            for tx in self._sorted_transactions()
            if tx.status is TransactionStatus.COMPLETED
        ]
        deltas: list[tuple[datetime, float]] = []
        for tx in completed:
            delta = self._signed_delta_rub(tx, owned)
            if delta == 0:
                continue
            moment = tx.processed_at or tx.updated_at or tx.created_at
            deltas.append((moment, delta))
        opening = round(current - sum(delta for _, delta in deltas), 2)
        start = deltas[0][0] if deltas else self._now()
        points = [(start, opening)]
        running = opening
        for moment, delta in deltas:
            running = round(running + delta, 2)
            points.append((moment, running))
        return points

    def _signed_delta_rub(
        self, transaction: Transaction, owned: set[str] | None
    ) -> float:
        amount = self._amount_rub(transaction)
        fee = self._fee_rub(transaction)
        if owned is None:
            if transaction.tx_type.value == "external":
                return round(-(amount + fee), 2)
            return 0.0
        delta = 0.0
        if transaction.sender_id in owned:
            delta -= amount + fee
        if transaction.receiver_id in owned:
            delta += amount
        return round(delta, 2)

    def _amount_rub(self, transaction: Transaction) -> float:
        return round(float(transaction.amount) * self._rate(transaction), 2)

    def _fee_rub(self, transaction: Transaction) -> float:
        fee = float(transaction.transfer_fee)
        if not fee:
            return 0.0
        return round(fee * self._fee_rate(transaction), 2)

    def _fee_rate(self, transaction: Transaction) -> float:
        sender = self.bank._accounts.get(transaction.sender_id)
        if sender is not None:
            return float(self.bank.rates_to_rub.get(sender.currency, 1.0))
        return self._rate(transaction)

    def _rate(self, transaction: Transaction) -> float:
        return float(self.bank.rates_to_rub.get(transaction.currency, 1.0))

    def _account_row(self, account: object) -> dict[str, object]:
        portfolio = getattr(account, "portfolio", None)
        return {
            "account_id": getattr(account, "account_id"),
            "type": type(account).__name__,
            "status": getattr(account, "status").value,
            "balance": getattr(account, "balance"),
            "currency": getattr(account, "currency").value,
            "portfolio": dict(portfolio) if isinstance(portfolio, dict) else {},
        }

    def _transaction_row(self, transaction: Transaction) -> dict[str, object]:
        processed = transaction.processed_at
        return {
            "transaction_id": transaction.transaction_id,
            "type": transaction.tx_type.value,
            "status": transaction.status.value,
            "amount": transaction.amount,
            "currency": transaction.currency.value,
            "fee": transaction.transfer_fee,
            "sender_id": transaction.sender_id,
            "receiver_id": transaction.receiver_id,
            "reason": transaction.rejection_reason or "",
            "created_at": transaction.created_at.isoformat(),
            "processed_at": processed.isoformat() if processed else "",
        }

    def _tabular_rows(self, report: dict[str, Any]) -> list[dict[str, object]]:
        kind = report.get("kind")
        if kind == "bank":
            return list(report.get("ranking") or report.get("transactions") or [])
        if kind == "client":
            return list(report.get("transactions") or report.get("accounts") or [])
        if kind == "risk":
            return list(report.get("suspicious") or report.get("assessments") or [])
        return []

    @staticmethod
    def _csv_cell(value: object) -> object:
        if isinstance(value, (list, tuple, dict)):
            return json.dumps(_to_jsonable(value), ensure_ascii=False)
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    def _sorted_transactions(self) -> list[Transaction]:
        return sorted(
            self.transactions,
            key=lambda tx: tx.processed_at or tx.updated_at or tx.created_at,
        )

    def _now(self) -> datetime:
        if self.processor is not None:
            return self.processor._clock()
        return self.bank._clock()

    @staticmethod
    def _save_pie(plt: Any, path: str, counts: Counter[str], title: str) -> str:
        figure, axis = plt.subplots()
        labels = list(counts.keys()) or ["none"]
        sizes = list(counts.values()) or [1]
        axis.pie(sizes, labels=labels, autopct="%1.1f%%")
        axis.set_title(title)
        figure.tight_layout()
        figure.savefig(path)
        plt.close(figure)
        return os.path.abspath(path)

    @staticmethod
    def _save_bar(
        plt: Any,
        path: str,
        labels: list[str],
        values: list[float],
        title: str,
        ylabel: str,
    ) -> str:
        figure, axis = plt.subplots()
        axis.bar(labels, values)
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.tick_params(axis="x", rotation=30)
        figure.tight_layout()
        figure.savefig(path)
        plt.close(figure)
        return os.path.abspath(path)

    @staticmethod
    def _save_line(
        plt: Any,
        path: str,
        points: list[tuple[datetime, float]],
        title: str,
    ) -> str:
        figure, axis = plt.subplots()
        xs = [item[0] for item in points] or [datetime.now()]
        ys = [item[1] for item in points] or [0.0]
        axis.plot(xs, ys, marker="o")
        axis.set_title(title)
        axis.set_ylabel("RUB")
        figure.autofmt_xdate()
        figure.tight_layout()
        figure.savefig(path)
        plt.close(figure)
        return os.path.abspath(path)

