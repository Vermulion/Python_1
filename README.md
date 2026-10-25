# Bank Account — Python study project

Built step by step.

Python 3.11+ is enough for the bank, tests, and reports. Charts need **matplotlib**.

## Setup

Do **not** copy library folders into the project. Declare the extra package and install it into a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On Linux/macOS use `source .venv/bin/activate` instead of `.venv\Scripts\activate`.

`requirements.txt` lists only **matplotlib**. The rest of the project uses the standard library (`json`, `csv`, `unittest`, …). Do not commit `.venv/` or a full `pip freeze` of your global Python.

After install:

```bash
python main.py
python -m unittest test_report_builder.py
```

Demo files land in `demo_reports/` (TXT/JSON/CSV) and `demo_reports/charts/` (PNG). Those are generated output, not packages.


## Step 1 — `AbstractAccount`

Shared base for every account type:

- unique `account_id`
- `owner` data (`full_name`, `email`, `phone`)
- protected `_balance`
- `status`: `active`, `frozen`, `closed`
- abstract methods: `get_account_info`
- shared money operations: `deposit`, `withdraw`
- base checks: sum correctness, account status, no negative values, at most 2 decimal places

## Step 2 — `BankAccount`

Concrete account with extra rules:

- validation of owner, amount, and currency
- operations allowed only when status is `active`
- `AccountFrozenError`, `AccountClosedError`, `InvalidOperationError`, `InsufficientFundsError`
- `freeze` / `unfreeze` / `close`
- short UUID (8 hex chars) if account number is empty
- `currency`: `RUB`, `USD`, `EUR`, `KZT`, `CNY`
- `__str__`: account type, client, last 4 digits of the number, status, balance and currency

## Step 3 — extra account types

- `SavingsAccount`: `min_balance`, `monthly_rate`, `apply_monthly_interest`; withdrawals cannot go below `min_balance`
- `PremiumAccount`: increased `transaction_limit`, `overdraft_limit` (balance may go negative), `fixed_fee` charged on each withdrawal
- `InvestmentAccount`: portfolio split among `stocks`, `bonds`, `etf`; `invest(type, amount)`; `withdraw` takes cash only (portfolio is not withdrawable); `project_yearly_growth(growth_rates)` with a dict of type → annual rate (demo: stocks 10%, bonds 4%, etf 7%)
- validation: active account, positive amount, enough funds, known security type
- every account type overrides `__str__()`

## Step 4 — `Client` and `Bank`

`Client`:

- first name, middle name, surname, unique id, status (`active` / `blocked` / `closed`)
- contacts: phones, email, address
- list of accounts
- age verification: must be 18 or older

`Bank`:

- `add_client()`, `authenticate_client(client_id, email)`
- `open_account()`, `close_account()`, `freeze_account()`, `unfreeze_account()`
- `search_accounts()` by account id, client, status, and/or type

## Step 5 — protection, totals, ranking

Protection:

- 3 failed authentications block the client (`auth_locked` tag)
- suspicious actions are tagged on the client and logged on the bank (`failed_auth`, `auth_locked`, `night_operation`, `unknown_client`)
- bank operations (`open` / `close` / `freeze` / `unfreeze`) and transfers are prohibited from 00:00 until 05:00

Additional:

- `get_total_balance()` — client or whole bank, converted via FX rates to RUB (or another currency)
- `get_clients_ranking()` — clients ordered by converted total, richest first

## Step 6 — transactions

`Transaction`:

- id, type (`internal` / `external`), amount, currency, transfer fee
- sender, receiver
- status, rejection reason, timestamps (`created_at` is a label; `execute_at` is the planned run time)

`TransactionQueue`:

- add to queue, priority, pending list, cancellation
- `pop_next()` returns only due transfers; deferred ones stay queued until `execute_at`

`TransactionProcessor`:

- outer-transfer fees, currency conversion, retries, error log
- no negative balance except premium overdraft
- no transfers from or to frozen accounts
- no transfers from 00:00 until 05:00 (night is not only a risk signal)
- fee on outer (external) transactions

## Step 7 — audit log and risk analyzer

`AuditLog`:

- importance levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- in-memory storage, save/load JSON-lines file, optional auto-save
- filtration by level, source, client, account, transaction, and time

`RiskAnalyzer`:

- flags large sums, frequent transfers, payments to new accounts, and night transfers (00:00–05:00)
- risk levels: `low`, `middle`, `high`
- the bank blocks `high` (dangerous) transactions and all night transfers before money moves

Audit reports:

- suspicious transactions
- client risk profile
- error statistics

## Step 8 — reports and charts

`ReportBuilder` turns bank, client, and risk data into files and plots:

- reports: by client, by bank, by risks
- formats: TXT, JSON, CSV via `export_to_txt()`, `export_to_json()`, `export_to_csv()`
- charts (matplotlib): pie, bar, and a balance-movement graph via `save_charts()`
- `export_all()` writes the three reports plus PNGs into one folder

## Run the demo

```bash
python main.py
```

`main.py` runs a full-system scenario (`bank_demo.py`):

- 8 clients and 15 accounts (checking, savings, premium, investment; one frozen)
- 40 queued transfers (day + night), one cancelled before execution
- mixed FX, external fees, frozen/unknown/overdraft failures
- risk screening: night, large-sum, and new-counterparty transfers; high risk is blocked
- user cases: client accounts, payment history, suspicious list
- reports: top-3 clients, transaction statistics, total bank balance
- `ReportBuilder` writes TXT/JSON/CSV plus pie, bar, and balance charts under `demo_reports/`
- audit trail written to `demo_audit.jsonl`

## Run tests

```bash
python -m unittest test_abstract_account.py test_bank_account.py test_savings_account.py test_premium_account.py test_investment_account.py test_client.py test_bank.py test_bank_scenario.py test_transaction.py test_audit_log.py test_risk_analyzer.py test_report_builder.py
```
