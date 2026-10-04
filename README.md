# Bank Account — Python study project

Built step by step.

## Step 1 — `AbstractAccount`

Shared base for every account type:

- unique `account_id`
- `owner` data (`full_name`, `email`, `phone`)
- protected `_balance`
- `status`: `active`, `frozen`, `closed`
- abstract methods: `deposit`, `withdraw`, `get_account_info`

You cannot create `AbstractAccount` directly. A later step will add a concrete class.

## Run the demo

```bash
python main.py
```

## Run tests

```bash
python -m unittest test_abstract_account.py
```
