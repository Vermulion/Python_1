"""Full-system demo: bank, clients, queue, risk checks, and reports."""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from bank import Bank
from client import Client, Contacts
from report_builder import ReportBuilder
from transaction import (
    Transaction,
    TransactionProcessor,
    TransactionQueue,
    TransactionStatus,
)


class DemoClock:
    """Mutable clock so daytime and night batches can share one processor."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _contacts(email: str, phone: str, address: str = "") -> Contacts:
    return Contacts(email=email, phones=[phone], address=address)


def _section(title: str) -> None:
    print(f"\n{'=' * 72}")
    print(title)
    print("=" * 72)


def _enqueue(
    queue: TransactionQueue,
    specs: list[tuple],
    *,
    created_at: datetime,
    execute_at: datetime | None = None,
) -> None:
    planned = execute_at if execute_at is not None else created_at
    for tx_id, sender, receiver, amount, currency, tx_type, priority in specs:
        queue.add(
            Transaction(
                sender_id=sender,
                receiver_id=receiver,
                amount=amount,
                currency=currency,
                tx_type=tx_type,
                transaction_id=tx_id,
                priority=priority,
                created_at=created_at,
                execute_at=planned,
            )
        )


def _history(results: list[Transaction], account_id: str) -> list[Transaction]:
    return [
        tx
        for tx in results
        if tx.sender_id == account_id or tx.receiver_id == account_id
    ]


def _transaction_statistics(results: list[Transaction]) -> dict[str, object]:
    by_status = Counter(tx.status.value for tx in results)
    by_type = Counter(tx.tx_type.value for tx in results)
    completed = [tx for tx in results if tx.status is TransactionStatus.COMPLETED]
    return {
        "total": len(results),
        "by_status": dict(by_status),
        "by_type": dict(by_type),
        "completed_volume": round(sum(tx.amount for tx in completed), 2),
        "completed_fees": round(sum(tx.transfer_fee for tx in completed), 2),
        "rejected": by_status.get("rejected", 0),
        "cancelled": by_status.get("cancelled", 0),
    }


def build_bank(clock: DemoClock) -> Bank:
    bank = Bank("Northern Demo Bank", clock=clock)
    people = [
        ("CL-ALICE", "Alice", "Marie", "Smith", "1990-01-15", "alice@demo.bank", "+79991111111", "Moscow"),
        ("CL-BOB", "Bob", "", "Jones", "1985-05-05", "bob@demo.bank", "+79992222222", "Kazan"),
        ("CL-CAROL", "Carol", "Ann", "Lee", "1992-03-20", "carol@demo.bank", "+79993333333", "Sochi"),
        ("CL-DANA", "Dana", "", "Kim", "1988-07-12", "dana@demo.bank", "+79994444444", "Novosibirsk"),
        ("CL-EVAN", "Evan", "", "Wu", "1991-11-02", "evan@demo.bank", "+79995555555", "Vladivostok"),
        ("CL-FAY", "Fay", "", "Chen", "1987-04-18", "fay@demo.bank", "+79996666666", "Astana"),
        ("CL-GINA", "Gina", "", "Rossi", "1993-09-09", "gina@demo.bank", "+79997777777", "Rome"),
        ("CL-HUGO", "Hugo", "", "Park", "1984-12-01", "hugo@demo.bank", "+79998888888", "Berlin"),
    ]
    for client_id, first, middle, surname, birth, email, phone, city in people:
        bank.add_client(
            Client(
                first_name=first,
                middle_name=middle,
                surname=surname,
                birth_date=birth,
                contacts=_contacts(email, phone, city),
                client_id=client_id,
            )
        )

    openings = [
        ("CL-ALICE", "checking", "ALICE-RUB", "RUB", 80_000, {}),
        ("CL-ALICE", "premium", "ALICE-USD", "USD", 2_000, {"overdraft_limit": 500, "fixed_fee": 2}),
        ("CL-BOB", "savings", "BOB-EUR", "EUR", 200, {"min_balance": 10, "monthly_rate": 0.01}),
        ("CL-BOB", "checking", "BOB-RUB", "RUB", 8_000, {}),
        ("CL-CAROL", "investment", "CAROL-CNY", "CNY", 5_000, {}),
        ("CL-CAROL", "checking", "CAROL-RUB", "RUB", 6_000, {}),
        ("CL-DANA", "checking", "DANA-RUB", "RUB", 40_000, {}),
        ("CL-DANA", "premium", "DANA-USD", "USD", 1_500, {"overdraft_limit": 200, "fixed_fee": 1}),
        ("CL-EVAN", "savings", "EVAN-EUR", "EUR", 80, {"min_balance": 5, "monthly_rate": 0.01}),
        ("CL-FAY", "checking", "FAY-KZT", "KZT", 200_000, {}),
        ("CL-FAY", "investment", "FAY-RUB", "RUB", 10_000, {}),
        ("CL-GINA", "checking", "GINA-RUB", "RUB", 5_000, {}),
        ("CL-GINA", "savings", "GINA-SAV", "RUB", 2_000, {"min_balance": 100, "monthly_rate": 0.02}),
        ("CL-HUGO", "premium", "HUGO-EUR", "EUR", 3_000, {"overdraft_limit": 200, "fixed_fee": 3}),
        ("CL-GINA", "checking", "GINA-HOLD", "RUB", 500, {}),
    ]
    for client_id, kind, account_id, currency, balance, extra in openings:
        bank.open_account(
            client_id,
            kind,
            opening_balance=balance,
            account_id=account_id,
            currency=currency,
            **extra,
        )
    bank.freeze_account("GINA-HOLD")
    return bank


def daytime_specs() -> list[tuple]:
    """Ordinary transfers plus a few expected errors (frozen / overdraft / unknown)."""
    return [
        ("D01", "ALICE-RUB", "BOB-RUB", 500, "RUB", "internal", 50),
        ("D02", "ALICE-RUB", "CAROL-RUB", 300, "RUB", "internal", 49),
        ("D03", "BOB-RUB", "GINA-RUB", 200, "RUB", "internal", 48),
        ("D04", "DANA-RUB", "EVAN-EUR", 1_000, "RUB", "internal", 47),
        ("D05", "ALICE-USD", "DANA-USD", 50, "USD", "internal", 46),
        ("D06", "HUGO-EUR", "BOB-EUR", 20, "EUR", "internal", 45),
        ("D07", "FAY-KZT", "GINA-RUB", 10_000, "KZT", "internal", 44),
        ("D08", "CAROL-CNY", "FAY-RUB", 200, "CNY", "internal", 43),
        ("D09", "GINA-SAV", "GINA-RUB", 150, "RUB", "internal", 42),
        ("D10", "ALICE-RUB", "SWIFT-EU", 800, "RUB", "external", 41),
        ("D11", "BOB-RUB", "ALICE-RUB", 120, "RUB", "internal", 40),
        ("D12", "DANA-USD", "ALICE-USD", 15, "USD", "internal", 39),
        ("D13", "CAROL-RUB", "BOB-RUB", 250, "RUB", "internal", 38),
        ("D14", "HUGO-EUR", "EVAN-EUR", 30, "EUR", "internal", 37),
        ("D15", "FAY-RUB", "DANA-RUB", 400, "RUB", "internal", 36),
        ("D16", "ALICE-RUB", "GINA-RUB", 90, "RUB", "internal", 35),
        ("D17", "BOB-EUR", "HUGO-EUR", 5, "EUR", "internal", 34),
        ("D18", "DANA-RUB", "CAROL-RUB", 220, "RUB", "internal", 33),
        ("D19", "GINA-RUB", "FAY-RUB", 80, "RUB", "internal", 32),
        ("D20", "ALICE-USD", "SWIFT-US", 25, "USD", "external", 31),
        ("D21", "CAROL-RUB", "GINA-SAV", 60, "RUB", "internal", 30),
        ("D22", "HUGO-EUR", "DANA-RUB", 10, "EUR", "internal", 29),
        ("D23", "FAY-KZT", "BOB-RUB", 5_000, "KZT", "internal", 28),
        ("D24", "ALICE-RUB", "FAY-RUB", 70, "RUB", "internal", 27),
        ("D25", "BOB-RUB", "DANA-RUB", 40, "RUB", "internal", 26),
        ("D26", "GINA-HOLD", "ALICE-RUB", 50, "RUB", "internal", 25),
        ("D27", "EVAN-EUR", "ALICE-RUB", 200, "EUR", "internal", 24),
        ("D28", "CAROL-RUB", "MISSING-ACC", 10, "RUB", "internal", 23),
        ("D29", "GINA-SAV", "ALICE-RUB", 1_950, "RUB", "internal", 22),
        ("D30", "DANA-USD", "BOB-RUB", 80, "USD", "internal", 21),
        ("D31", "ALICE-RUB", "BOB-RUB", 45, "RUB", "internal", 20),
        ("D32", "FAY-RUB", "GINA-RUB", 55, "RUB", "internal", 19),
        ("CXL1", "ALICE-RUB", "BOB-RUB", 10, "RUB", "internal", 5),
    ]


def night_specs() -> list[tuple]:
    """Night / large / new-account transfers: middle and high risk."""
    return [
        ("N01", "ALICE-RUB", "OFFSHORE-1", 60_000, "RUB", "external", 90),
        ("N02", "DANA-USD", "GHOST-ACC", 800, "USD", "external", 89),
        ("N03", "HUGO-EUR", "SHADOW-9", 600, "EUR", "external", 88),
        ("N04", "FAY-KZT", "NEW-KZT", 300_000, "KZT", "external", 87),
        ("N05", "ALICE-USD", "OFFSHORE-2", 700, "USD", "external", 86),
        ("N06", "CAROL-CNY", "NEW-CNY", 4_200, "CNY", "external", 85),
        ("N07", "DANA-RUB", "BOB-RUB", 100, "RUB", "internal", 84),
        ("N08", "GINA-RUB", "NEW-GINA", 20, "RUB", "external", 83),
    ]


def run_demo() -> None:
    day = datetime(2026, 6, 15, 12, 0)
    night = datetime(2026, 6, 16, 2, 0)
    clock = DemoClock(day)
    bank = build_bank(clock)
    queue = TransactionQueue()
    processor = TransactionProcessor(bank, queue, outer_fee_rate=0.01, clock=clock)

    _section("1. Initialization: bank, clients, accounts")
    print(f"  bank: {bank.name}")
    print(f"  clients: {len(bank._clients)}")
    print(f"  accounts: {len(bank._accounts)}")
    for client in bank._clients.values():
        print(f"  {client}")
        for account in client.accounts:
            print(f"     {account}")
    print("  frozen accounts:", [acc.account_id for acc in bank.search_accounts(status="frozen")])

    _section("2. Simulation: enqueue 41 transfers (day + night)")
    _enqueue(queue, daytime_specs(), created_at=day, execute_at=day)
    cancelled = queue.cancel("CXL1", at=day)
    print(f"  cancelled before run: {cancelled.transaction_id} [{cancelled.status.value}]")
    _enqueue(queue, night_specs(), created_at=day, execute_at=night)
    pending = queue.pending_transactions()
    print(f"  queued (pending): {len(pending)}")
    print("  first 8 in priority order:", [tx.transaction_id for tx in pending[:8]])
    print("  last 5 in priority order:", [tx.transaction_id for tx in pending[-5:]])
    print(
        "  deferred until night:",
        sum(1 for tx in pending if tx.execute_at == night),
    )

    _section("3. Logging: execution, deviations, audit")
    clock.now = day
    day_results = processor.process_all()
    clock.now = night
    night_results = processor.process_all()
    results = day_results + night_results
    print(f"  executed daytime: {len(day_results)}")
    print(f"  executed night: {len(night_results)}")
    print("  sample of completed transfers:")
    completed = [tx for tx in results if tx.status is TransactionStatus.COMPLETED]
    for tx in completed[:8]:
        print(f"    {tx}")
    print(f"    ... {len(completed)} completed in total")
    print("  deviations / rejections:")
    for tx in results:
        if tx.status is not TransactionStatus.COMPLETED:
            print(f"    {tx}")
    print("  audit sample (WARNING+):")
    for entry in processor.audit_log.filter(min_level="WARNING")[:8]:
        print(f"    {entry}")
    print(f"  audit records total: {len(processor.audit_log.entries())}")
    print(f"  processor error log: {len(processor.error_log)}")
    saved = processor.audit_log.save("demo_audit.jsonl")
    print(f"  audit file: {saved}")

    _section("4. User cases: accounts, history, suspicious transfers")
    alice = bank._require_client("CL-ALICE")
    print(f"  client {alice.full_name} ({alice.client_id})")
    for account in alice.accounts:
        print(f"    {account}")
        history = _history(results, account.account_id)
        print(f"      history ({len(history)}):")
        for tx in history[:6]:
            print(f"        {tx}")
    print("  suspicious transactions (middle+):")
    for row in processor.reporter.suspicious_transactions():
        print(
            f"    {row['transaction_id']} {row['risk_level']} "
            f"{row['sender_id']} -> {row['receiver_id']} "
            f"signals={row['signals']} amount_rub={row['amount_rub']}"
        )
    print("  Alice risk profile:", processor.reporter.client_risk_profile("CL-ALICE"))
    print("  Dana risk profile:", processor.reporter.client_risk_profile("CL-DANA"))

    _section("5. Reports")
    print("  top-3 clients:")
    for row in bank.get_clients_ranking()[:3]:
        print(
            f"    {row['full_name']} ({row['client_id']}): "
            f"{row['total_balance']} {row['currency']}"
        )
    stats = _transaction_statistics(results + [cancelled])
    print("  transaction statistics:", stats)
    print("  error statistics:", processor.reporter.error_statistics())
    print(f"  bank total balance: {bank.get_total_balance()} RUB")
    print(f"  Alice total: {bank.get_total_balance('CL-ALICE')} RUB")
    print(f"  Dana total: {bank.get_total_balance('CL-DANA')} RUB")
    builder = ReportBuilder(
        bank,
        processor,
        transactions=results + [cancelled],
        output_dir="demo_reports",
    )
    alice_report = builder.client_report("CL-ALICE")
    paths = {
        "alice_json": builder.export_to_json(
            "demo_reports/client_alice.json", alice_report
        ),
        "alice_csv": builder.export_to_csv(
            "demo_reports/client_alice.csv", alice_report
        ),
        "bank_json": builder.export_to_json("demo_reports/bank_report.json"),
        "bank_csv": builder.export_to_csv("demo_reports/bank_report.csv"),
        "bank_txt": builder.export_to_txt("demo_reports/bank_report.txt"),
        "risk_json": builder.export_to_json(
            "demo_reports/risk_report.json", builder.risk_report()
        ),
        "risk_csv": builder.export_to_csv(
            "demo_reports/risk_report.csv", builder.risk_report()
        ),
    }
    charts = builder.save_charts("demo_reports/charts")
    print("  exported reports:")
    for name, path in paths.items():
        print(f"    {name}: {path}")
    print("  charts:")
    for name, path in charts.items():
        print(f"    {name}: {path}")


if __name__ == "__main__":
    run_demo()

