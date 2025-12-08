from app import app, db
from models import RecurringTransaction, Transaction
from currency_utils import CurrencyConverter

def verify_spending_logic():
    with app.app_context():
        # Get an income source
        inc = RecurringTransaction.query.filter_by(type='income').first()
        if not inc:
            print("No income source found.")
            return

        print(f"Income Source: {inc.description} ({inc.amount} {inc.currency})")
        
        # Calculate spent via DB logic identical to app.py
        inc_spent = 0
        linked_transactions = Transaction.query.filter_by(income_source_id=inc.id).all()
        for t in linked_transactions:
            inc_spent += CurrencyConverter.convert(t.amount, t.currency, inc.currency)
            
        print(f"Calculated Spent: {inc_spent}")
        remaining = inc.amount - inc_spent
        print(f"Calculated Remaining: {remaining}")

        # Check against a known transaction if possible
        # We added 'EVN' transaction in previous steps, let's see if we can link it or if it is linked
        # Previous step verification showed "EVN (Edited) - 2924.0" (amount)
        # But we didn't check if it was linked to an income source in that verification script.
        # We need to ensure we have at least one linked transaction for a meaningful test.
        
        if len(linked_transactions) == 0:
            print("No linked transactions found. Creating one for test...")
            # Create a dummy transaction linked to this source
            from datetime import datetime
            t = Transaction(
                amount=100, 
                currency=inc.currency, 
                description="Test Spend", 
                type='expense', 
                date=datetime.utcnow(),
                user_id=inc.household_id, # Assuming single user household for test
                household_id=inc.household_id,
                income_source_id=inc.id,
                category_id=None
            )
            db.session.add(t)
            db.session.commit()
            print("Created test transaction of 100.")
            
            # Recalculate
            inc_spent += 100
            print(f"New Spent Should Be: {inc_spent}")
            
            # Cleanup
            db.session.delete(t)
            db.session.commit()
            print("Cleaned up test transaction.")

if __name__ == "__main__":
    verify_spending_logic()
