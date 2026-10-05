"""Step 2 demo: BankAccount validation, status rules, and currency."""

from abstract_account import Owner
from bank_account import AccountClosedError, AccountFrozenError, BankAccount


def main() -> None:
    owner = Owner(
        full_name="Alice Smith",
        email="alice@example.com",
        phone="+79991234567",
    )
    account = BankAccount(owner, opening_balance=100, currency="RUB")
    print(account)

    account.deposit(50)
    account.withdraw(20)
    print("After operations:", account.get_account_info())

    account.freeze()
    try:
        account.withdraw(10)
    except AccountFrozenError as error:
        print(f"Frozen account blocked withdraw: {error}")

    account.unfreeze()
    account.close()
    try:
        account.deposit(5)
    except AccountClosedError as error:
        print(f"Closed account blocked deposit: {error}")


if __name__ == "__main__":
    main()
