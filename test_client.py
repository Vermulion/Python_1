import unittest
from datetime import date

from abstract_account import AbstractAccount
from client import Client, ClientStatus, Contacts, UnderageClientError


class ClientTests(unittest.TestCase):
    def setUp(self) -> None:
        AbstractAccount._used_ids.clear()
        Client._used_ids.clear()
        self.contacts = Contacts(
            email="alice@example.com",
            phones=["+79991234567"],
            address="Moscow",
        )

    def test_stores_identity_contacts_status_and_accounts(self) -> None:
        client = Client(
            first_name="Alice",
            middle_name="Marie",
            surname="Smith",
            birth_date="1990-01-15",
            contacts=self.contacts,
            client_id="CL-1",
        )
        self.assertEqual(client.full_name, "Alice Marie Smith")
        self.assertEqual(client.client_id, "CL-1")
        self.assertEqual(client.status, ClientStatus.ACTIVE)
        self.assertEqual(client.contacts.email, "alice@example.com")
        self.assertEqual(client.contacts.phones, ["+79991234567"])
        self.assertEqual(client.accounts, [])
        self.assertGreaterEqual(client.age, 18)

    def test_rejects_underage_client(self) -> None:
        today = date.today()
        birth = date(today.year - 17, today.month, today.day)
        with self.assertRaises(UnderageClientError):
            Client("Bob", "Jones", birth, self.contacts)

    def test_rejects_invalid_contacts(self) -> None:
        with self.assertRaises(ValueError):
            Contacts(email="not-an-email", phones=["+79991234567"])
        with self.assertRaises(ValueError):
            Contacts(email="alice@example.com", phones=["123"])

    def test_client_ids_must_be_unique(self) -> None:
        Client("Alice", "Smith", "1990-01-15", self.contacts, client_id="CL-1")
        with self.assertRaises(ValueError):
            Client("Bob", "Jones", "1985-05-05", self.contacts, client_id="CL-1")

    def test_as_owner_uses_full_name_and_first_phone(self) -> None:
        client = Client("Alice", "Smith", "1990-01-15", self.contacts)
        owner = client.as_owner()
        self.assertEqual(owner.full_name, "Alice Smith")
        self.assertEqual(owner.email, "alice@example.com")
        self.assertEqual(owner.phone, "+79991234567")


if __name__ == "__main__":
    unittest.main()
