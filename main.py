"""Step 3 demo: BankAccount plus Savings / Premium / Investment types."""

from datetime import datetime

from abstract_account import Owner
from bank import Bank
from bank_account import AccountFrozenError, BankAccount, InvalidOperationError
from client import Client, Contacts
from investment_account import DEMO_GROWTH_RATES, InvestmentAccount
from premium_account import PremiumAccount
from savings_account import SavingsAccount


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

    savings = SavingsAccount(
        Owner("Carol Lee", email="carol@example.com", phone="+79991112233"),
        opening_balance=1000,
        account_id="SAV-3003",
        min_balance=100,
        monthly_rate=0.01,
    )
    premium = PremiumAccount(
        Owner("Dana Kim", email="dana@example.com", phone="+79994445566"),
        opening_balance=500,
        account_id="PREM-4004",
        transaction_limit=1_000_000,
        overdraft_limit=1_000,
        fixed_fee=5,
    )
    investment = InvestmentAccount(
        Owner("Evan Wu", email="evan@example.com", phone="+79997778899"),
        opening_balance=800,
        account_id="INV-5005",
    )

    print("\nExtra account types:")
    print(" ", savings)
    print(" ", premium)
    print(" ", investment)
    savings.apply_monthly_interest()
    print("  savings after monthly interest:", savings.get_account_info())

    print("\nPremium overdraft and fee:")
    print(f"  before withdraw: {premium.get_account_info()}")
    premium.withdraw(520)
    print("  withdrew 520 (plus fixed fee 5)")
    print(f"  after: {premium.get_account_info()}")
    print(" ", premium)

    print("\nInvestment portfolio:")
    investment.invest("stocks", 300)
    investment.invest("bonds", 200)
    investment.invest("etf", 100)
    print(" ", investment)
    print("  info:", investment.get_account_info())
    print("  demo rates:", DEMO_GROWTH_RATES)
    print("  projected yearly growth:", investment.project_yearly_growth(DEMO_GROWTH_RATES))

    print("\nBank, clients, and account management:")
    bank = Bank("Study Bank", clock=lambda: datetime(2026, 6, 15, 12, 0))
    carol = Client(
        first_name="Carol",
        middle_name="Ann",
        surname="Lee",
        birth_date="1992-03-20",
        contacts=Contacts(
            email="carol@example.com",
            phones=["+79991112233", "+79991110000"],
            address="Kazan",
        ),
        client_id="CL-CAROL",
    )
    bank.add_client(carol)
    print("  added:", carol)
    verified = bank.authenticate_client("CL-CAROL", "carol@example.com")
    print("  authenticated:", verified.full_name)
    bank_savings = bank.open_account(
        "CL-CAROL",
        "savings",
        opening_balance=1000,
        account_id="BANK-SAV-1",
        min_balance=100,
        monthly_rate=0.01,
    )
    bank_premium = bank.open_account(
        "CL-CAROL",
        "premium",
        opening_balance=500,
        account_id="BANK-PREM-1",
    )
    print("  opened:", bank_savings)
    print("  opened:", bank_premium)
    bank.freeze_account("BANK-PREM-1")
    print("  frozen premium:", bank.search_accounts(status="frozen"))
    bank.unfreeze_account("BANK-PREM-1")
    bank.close_account("BANK-PREM-1")
    print("  carol accounts:", bank.search_accounts(client_id="CL-CAROL"))

    print("\nProtection, totals, and ranking:")
    dana = Client(
        first_name="Dana",
        surname="Kim",
        birth_date="1988-07-12",
        contacts=Contacts(
            email="dana@example.com",
            phones=["+79994445566"],
            address="Novosibirsk",
        ),
        client_id="CL-DANA",
    )
    evan = Client(
        first_name="Evan",
        surname="Wu",
        birth_date="1991-11-02",
        contacts=Contacts(
            email="evan@example.com",
            phones=["+79997778899"],
            address="Vladivostok",
        ),
        client_id="CL-EVAN",
    )
    bank.add_client(dana)
    bank.add_client(evan)
    bank.open_account("CL-DANA", "checking", opening_balance=200, account_id="DANA-RUB", currency="RUB")
    bank.open_account("CL-DANA", "premium", opening_balance=50, account_id="DANA-USD", currency="USD")
    bank.open_account("CL-EVAN", "savings", opening_balance=30, account_id="EVAN-EUR", currency="EUR", min_balance=5, monthly_rate=0.01)
    print("  dana total RUB:", bank.get_total_balance("CL-DANA"))
    print("  bank total RUB:", bank.get_total_balance())
    print("  ranking:")
    for row in bank.get_clients_ranking():
        print("   ", row)

    print("\nFailed authentication lockout:")
    for attempt in range(1, 4):
        try:
            bank.authenticate_client("CL-EVAN", "wrong@example.com")
        except InvalidOperationError as error:
            print(f"  attempt {attempt}: {error}")
    print("  evan:", evan)
    print("  tags:", evan.tags)
    print("  suspicious events:", [event["tag"] for event in bank.suspicious_events])

    print("\nFreeze a multi-currency account:")
    bank.freeze_account("DANA-USD")
    print("  frozen:", bank.search_accounts(status="frozen"))
    bank.unfreeze_account("DANA-USD")
    print("  after unfreeze:", bank.search_accounts(account_id="DANA-USD")[0].status.value)



if __name__ == "__main__":
    main()
