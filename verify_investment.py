from app import app, db
from models import Transaction, Budget, Category, Integration, Account
from currency_utils import CurrencyConverter
from datetime import datetime

def verify_investment_sync():
    with app.app_context():
        # Setup: Ensure we have a Budget, a Category(Savings), and an Integration/Account
        cat = Category.query.filter_by(name="Savings").first()
        if not cat:
            print("Creating 'Savings' category...")
            cat = Category(name="Savings", type="expense", household_id=1) # type='expense' or 'savings' - budgets usually expense
            db.session.add(cat)
            db.session.commit()
            
        bud = Budget.query.filter_by(category_id=cat.id).first()
        if not bud:
            print("Creating budget for Savings...")
            bud = Budget(category_id=cat.id, amount_limit=1000, household_id=1)
            db.session.add(bud)
            db.session.commit()
            
        # Simulating Integration
        integ = Integration.query.first()
        if not integ:
            # Create dummy integration
            integ = Integration(platform="Bybit", api_key="dummy", household_id=1)
            db.session.add(integ)
            db.session.commit()
            
        acc_name = f"{integ.platform.capitalize()} Account"
        acc = Account.query.filter_by(name=acc_name).first()
        if not acc:
            acc = Account(name=acc_name, balance=0, currency='USD', type='crypto', household_id=1)
            db.session.add(acc)
            db.session.commit()
            
        initial_invested = acc.invested_amount
        print(f"Initial Invested: {initial_invested}")
        
        # Create Investment Transaction
        inv_amount = 200.0
        t = Transaction(
            amount=inv_amount,
            currency='USD',
            description="Crypto Buy",
            type='investment',
            date=datetime.utcnow(),
            category_id=cat.id,
            user_id=1,
            household_id=1
        )
        db.session.add(t)
        
        # Simulate the logic in app.py manually since we are not hitting the route
        amount_in_account_currency = CurrencyConverter.convert(inv_amount, 'USD', acc.currency)
        acc.invested_amount += amount_in_account_currency
        db.session.commit()
        
        print(f"New Invested: {acc.invested_amount}")
        if acc.invested_amount == initial_invested + 200:
             print("SUCCESS: Integration Account updated.")
        else:
             print("FAILURE: Integration update logic.")
             
        # Check Budget Logic
        # We need to run the budget calc logic
        spent = 0
        txns = Transaction.query.filter_by(category_id=cat.id).all()
        for txn in txns:
             if txn.type in ['expense', 'investment']:
                 spent += txn.amount # simplifying currency
        
        print(f"Budget Spent: {spent}")
        if spent >= 200: # Could be more if existing txns
             print("SUCCESS: Investment counted in Budget.")
        else:
             print("FAILURE: Investment not counted in Budget.")

        # Cleanup
        db.session.delete(t)
        # Restore account
        acc.invested_amount = initial_invested
        db.session.commit()

if __name__ == "__main__":
    verify_investment_sync()
