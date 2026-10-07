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

## Run the demo

```bash
python main.py
```

## Run tests

```bash
python -m unittest test_abstract_account.py test_bank_account.py test_savings_account.py test_premium_account.py test_investment_account.py
```
