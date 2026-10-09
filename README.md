# Bank Account — Python study project

Built step by step.

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
- bank operations (`open` / `close` / `freeze` / `unfreeze`) are prohibited from 00:00 until 05:00

Additional:

- `get_total_balance()` — client or whole bank, converted via FX rates to RUB (or another currency)
- `get_clients_ranking()` — clients ordered by converted total, richest first

## Step 6 — transactions

`Transaction`:

- id, type (`internal` / `external`), amount, currency, transfer fee
- sender, receiver
- status, rejection reason, timestamps

`TransactionQueue`:

- add to queue, priority, pending list, cancellation

`TransactionProcessor`:

- outer-transfer fees, currency conversion, retries, error log
- no negative balance except premium overdraft
- no transfers from or to frozen accounts
- fee on outer (external) transactions

## Run the demo

```bash
python main.py
```

## Run tests

```bash
python -m unittest test_abstract_account.py test_bank_account.py test_savings_account.py test_premium_account.py test_investment_account.py test_client.py test_bank.py test_bank_scenario.py test_transaction.py
```
