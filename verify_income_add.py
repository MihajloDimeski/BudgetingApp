from app import app, db
from models import RecurringTransaction, Transaction
from currency_utils import CurrencyConverter

def verify_income_addition():
    with app.app_context():
        # Get an income source
        inc = RecurringTransaction.query.filter_by(type='income').first()
        if not inc:
            print("No income source found.")
            return

        # Initial calculation
        inc_spent = 0
        linked = Transaction.query.filter_by(income_source_id=inc.id).all()
        for t in linked:
            amt = CurrencyConverter.convert(t.amount, t.currency, inc.currency)
            if t.type == 'income':
                inc_spent -= amt
            else:
                inc_spent += amt
        
        initial_remaining = inc.amount - inc_spent
        print(f"Initial Remaining: {initial_remaining}")
        
        # Add a one-time income (Bonus)
        from datetime import datetime
        bonus = Transaction(
            amount=500.0,
            currency=inc.currency,
            description="Bonus Cash",
            type='income',
            date=datetime.utcnow(),
            user_id=inc.household.users[0].id,
            household_id=inc.household.id,
            income_source_id=inc.id
        )
        db.session.add(bonus)
        db.session.commit()
        print("Added Bonus of 500.")
        
        # Recalculate
        inc_spent_new = 0
        linked_new = Transaction.query.filter_by(income_source_id=inc.id).all()
        for t in linked_new:
            amt = CurrencyConverter.convert(t.amount, t.currency, inc.currency)
            if t.type == 'income':
                inc_spent_new -= amt
            else:
                inc_spent_new += amt
        
        new_remaining = inc.amount - inc_spent_new
        print(f"New Remaining: {new_remaining}")
        
        if new_remaining == initial_remaining + 500:
            print("SUCCESS: Remaining balance increased by bonus amount.")
        else:
            print("FAILURE: Calculation incorrect.")
            
        # Cleanup
        db.session.delete(bonus)
        db.session.commit()

if __name__ == "__main__":
    verify_income_addition()
