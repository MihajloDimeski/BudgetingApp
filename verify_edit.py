from app import app, db
from models import Transaction
from datetime import datetime

def verify_update():
    with app.app_context():
        # Get latest transaction
        t = Transaction.query.order_by(Transaction.id.desc()).first()
        if not t:
            print("No transaction.")
            return

        print(f"Original: {t.description} - {t.amount}")
        
        # Simulate update
        t.description = t.description + " (Edited)"
        t.amount = t.amount + 10
        db.session.commit()
        
        t_upd = Transaction.query.get(t.id)
        if "Edited" in t_upd.description:
             print(f"Update SUCCESS: {t_upd.description} - {t_upd.amount}")
        else:
             print("Update FAILED")

if __name__ == "__main__":
    verify_update()
