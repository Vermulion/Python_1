import unittest

from abstract_account import AbstractAccount, AccountStatus, Owner


class DummyAccount(AbstractAccount):
    """Minimal subclass so tests can create an account object."""

    def deposit(self, amount: float) -> float:
        self._balance += amount
        return self._balance

    def withdraw(self, amount: float) -> float:
        self._balance -= amount
        return self._balance

    def get_account_info(self) -> dict[str, object]:
        return {
            "account_id": self.account_id,
            "owner": self.owner.full_name,
            "balance": self._balance,
            "status": self.status.value,
        }


class AbstractAccountTests(unittest.TestCase):
    def setUp(self) -> None:
        AbstractAccount._used_ids.clear()

    def test_cannot_instantiate_abstract_class(self) -> None:
        owner = Owner("Alice")
        with self.assertRaises(TypeError):
            AbstractAccount(owner)

    def test_stores_unique_id_owner_protected_balance_and_status(self) -> None:
        owner = Owner("Alice Smith", email="alice@example.com", phone="123")
        account = DummyAccount(owner, opening_balance=50, account_id="ACC-1")

        self.assertEqual(account.account_id, "ACC-1")
        self.assertEqual(account.owner.full_name, "Alice Smith")
        self.assertEqual(account._balance, 50)
        self.assertEqual(account.status, AccountStatus.ACTIVE)
        self.assertTrue(hasattr(account, "_balance"))

    def test_account_ids_must_be_unique(self) -> None:
        DummyAccount(Owner("Alice"), account_id="ACC-1")
        with self.assertRaises(ValueError):
            DummyAccount(Owner("Bob"), account_id="ACC-1")

    def test_generated_ids_are_unique(self) -> None:
        first = DummyAccount(Owner("Alice"))
        second = DummyAccount(Owner("Bob"))
        self.assertNotEqual(first.account_id, second.account_id)

    def test_empty_owner_name_is_invalid(self) -> None:
        with self.assertRaises(ValueError):
            Owner("  ")

    def test_negative_opening_balance_is_invalid(self) -> None:
        with self.assertRaises(ValueError):
            DummyAccount(Owner("Alice"), opening_balance=-1)


if __name__ == "__main__":
    unittest.main()
