"""Step 1 demo: AbstractAccount cannot be created directly."""

from abstract_account import AbstractAccount, Owner


def main() -> None:
    owner = Owner(full_name="Alice Smith", email="alice@example.com")
    print(f"Owner ready: {owner.full_name}")

    try:
        AbstractAccount(owner=owner, opening_balance=100)
    except TypeError as error:
        print("AbstractAccount is abstract, as expected:")
        print(f"  {error}")


if __name__ == "__main__":
    main()
