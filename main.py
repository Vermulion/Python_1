"""Step 2 demo: BankAccount validation, status rules, and currency."""

from abstract_account import Owner
from bank_account import AccountFrozenError, BankAccount


def main() -> None:
    active_owner = Owner(
        full_name="Alice Smith",
        email="alice@example.com",
        phone="+79991234567",
    )
    frozen_owner = Owner(
        full_name="Bob Jones",
        email="bob@example.com",
        phone="+79997654321",
    )

    active_account = BankAccount(
        active_owner,
        opening_balance=100,
        account_id="ACC-1001",
        currency="RUB",
    )
    frozen_account = BankAccount(
        frozen_owner,
        opening_balance=200,
        account_id="ACC-2002",
        currency="USD",
    )
    frozen_account.freeze()

    print("Created accounts:")
    print(" ", active_account)
    print(" ", frozen_account)

    print("\nTrying operations on frozen account:")
    try:
        frozen_account.deposit(50)
    except AccountFrozenError as error:
        print(f"  deposit blocked: {error}")
    try:
        frozen_account.withdraw(10)
    except AccountFrozenError as error:
        print(f"  withdraw blocked: {error}")
    print("  frozen account after blocked ops:", frozen_account.get_account_info())

    print("\nAdding money and withdrawing from valid (active) account:")
    print(f"  before: {active_account.get_account_info()}")
    active_account.deposit(50)
    print("  deposited 50")
    active_account.withdraw(20)
    print("  withdrew 20")
    print(f"  after:  {active_account.get_account_info()}")


if __name__ == "__main__":
    main()
