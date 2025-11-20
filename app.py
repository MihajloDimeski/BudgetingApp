import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from extensions import db
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from datetime import datetime, timedelta
import time
from sqlalchemy.exc import OperationalError

# Import models
from models import User, Household, Account, Integration, Category, Budget, Transaction, RecurringTransaction, BalanceHistory
from currency_utils import CurrencyConverter
from integrations.bybit_client import BybitClient
from integrations.trading212_client import Trading212Client

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_secret')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'auth'

@app.context_processor
def inject_currency():
    def currency_symbol(currency_code):
        return CurrencyConverter.get_symbol(currency_code)
    return dict(currency_symbol=currency_symbol)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def wait_for_db(app):
    with app.app_context():
        retries = 5
        while retries > 0:
            try:
                db.engine.connect()
                print("Database connection successful!")
                return
            except OperationalError:
                retries -= 1
                print(f"Database not ready. Waiting... ({retries} retries left)")
                time.sleep(5)
        raise Exception("Could not connect to the database after multiple retries.")

with app.app_context():
    wait_for_db(app)
    db.create_all()

def sync_integrations_helper(household_id):
    household = Household.query.get(household_id)
    if not household:
        return

    integrations = household.integrations
    if not integrations:
        return

    print(f"=== SYNC START: Found {len(integrations)} integrations ===")
    
    for i in integrations:
        balance = 0.0
        client = None
        
        print(f"Processing integration: {i.platform}")
        
        try:
            if i.platform == 'bybit':
                client = BybitClient(i.api_key, i.api_secret)
            elif i.platform == 'trading212':
                client = Trading212Client(i.api_key, i.api_secret)
                
            if client:
                balance = client.get_balance()
                
                # Update or Create Account
                account_name = f"{i.platform.capitalize()} Account"
                account = Account.query.filter_by(name=account_name, household_id=household_id).first()
                
                if account:
                    account.balance = balance
                else:
                    account = Account(name=account_name, type='Investment', balance=balance, household_id=household_id)
                    db.session.add(account)
                    db.session.flush()
                
                # Record History
                history = BalanceHistory(
                    account_id=account.id,
                    balance=balance,
                    invested_amount=account.invested_amount,
                    date=datetime.utcnow()
                )
                db.session.add(history)
                
                # Update last_synced
                i.last_synced = datetime.utcnow()
                db.session.commit()
                
        except Exception as e:
            print(f"Error syncing {i.platform}: {e}")
            
    print("=== SYNC COMPLETE ===")

@app.route('/')
@login_required
def index():
    # Auto-refresh logic
    household = current_user.household
    integrations = household.integrations
    should_sync = False
    for i in integrations:
        if not i.last_synced or (datetime.utcnow() - i.last_synced).total_seconds() > 3600:
            should_sync = True
            break
            
    if should_sync:
        sync_integrations_helper(household.id)
        # Reload household to get updated data
        db.session.expire(household)

    # Dashboard calculations
    base_currency = household.base_currency
    
    # Net Worth
    net_worth = 0
    for account in household.accounts:
        net_worth += CurrencyConverter.convert(account.balance, account.currency, base_currency)
        
    # Income/Expenses
    transactions = Transaction.query.filter_by(household_id=household.id).order_by(Transaction.date.desc()).all()
    total_income = sum(t.amount_in_base_currency for t in transactions if t.type == 'income')
    total_expenses = sum(t.amount_in_base_currency for t in transactions if t.type == 'expense')
    
    recent_transactions = transactions[:5]
    
    return render_template('dashboard.html', 
                         net_worth=net_worth, 
                         total_income=total_income, 
                         total_expenses=total_expenses,
                         recent_transactions=recent_transactions)

@app.route('/set_currency', methods=['POST'])
@login_required
def set_currency():
    currency = request.form.get('currency')
    if currency in ['USD', 'EUR', 'MKD']:
        current_user.household.base_currency = currency
        
        # Recalculate transactions
        transactions = Transaction.query.filter_by(household_id=current_user.household.id).all()
        for t in transactions:
            t.amount_in_base_currency = CurrencyConverter.convert(t.amount, t.currency, currency)
            
        db.session.commit()
        flash(f'Currency switched to {currency}', 'success')
    
    return redirect(request.referrer or url_for('index'))

@app.route('/auth', methods=['GET'])
def auth():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('auth.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    user = User.query.filter_by(username=username).first()
    
    if user and check_password_hash(user.password_hash, password):
        login_user(user)
        return redirect(url_for('index'))
    
    flash('Invalid username or password')
    return redirect(url_for('auth'))

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')
    household_action = request.form.get('household_action')
    
    if User.query.filter_by(username=username).first():
        flash('Username already exists')
        return redirect(url_for('auth'))
        
    hashed_password = generate_password_hash(password)
    
    household = None
    if household_action == 'create':
        hh_name = request.form.get('household_name')
        base_currency = request.form.get('base_currency', 'USD')
        join_code = str(uuid.uuid4())[:8] # Simple 8-char code
        household = Household(name=hh_name, join_code=join_code, base_currency=base_currency)
        db.session.add(household)
        db.session.commit() # Commit to get ID
    elif household_action == 'join':
        join_code = request.form.get('join_code')
        household = Household.query.filter_by(join_code=join_code).first()
        if not household:
            flash('Invalid Join Code')
            return redirect(url_for('auth'))
            
    new_user = User(username=username, password_hash=hashed_password, household=household)
    db.session.add(new_user)
    db.session.commit()
    
    login_user(new_user)
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth'))

@app.route('/household')
@login_required
def household():
    household = current_user.household
    members = User.query.filter_by(household_id=household.id).all()
    return render_template('household.html', household=household, members=members)

@app.route('/remove_member/<int:user_id>')
@login_required
def remove_member(user_id):
    if user_id == current_user.id:
        flash('You cannot remove yourself from the household!', 'warning')
        return redirect(url_for('household'))
    
    user = User.query.get_or_404(user_id)
    if user.household_id != current_user.household_id:
        flash('User not found in your household!', 'warning')
        return redirect(url_for('household'))
    
    username = user.username
    user.household_id = None
    db.session.commit()
    
    flash(f'{username} has been removed from the household.', 'success')
    return redirect(url_for('household'))

@app.route('/transactions', methods=['GET', 'POST'])
@login_required
def transactions():
    if request.method == 'POST':
        amount = float(request.form.get('amount'))
        description = request.form.get('description')
        type = request.form.get('type')
        date_str = request.form.get('date')
        category_id = request.form.get('category_id')
        currency = request.form.get('currency', 'USD')
        
        date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.utcnow()
        
        base_currency = current_user.household.base_currency
        amount_in_base = CurrencyConverter.convert(amount, currency, base_currency)
        
        t = Transaction(
            amount=amount,
            currency=currency,
            amount_in_base_currency=amount_in_base,
            description=description,
            type=type,
            date=date,
            category_id=int(category_id) if category_id else None,
            user_id=current_user.id,
            household_id=current_user.household_id
        )
        db.session.add(t)
        db.session.commit()
        return redirect(url_for('transactions'))
    
    transactions = Transaction.query.filter_by(household_id=current_user.household_id).order_by(Transaction.date.desc()).all()
    recurring = RecurringTransaction.query.filter_by(household_id=current_user.household_id).all()
    categories = Category.query.filter_by(household_id=current_user.household_id).all()
    
    return render_template('transactions.html', transactions=transactions, recurring=recurring, categories=categories, today=datetime.utcnow().strftime('%Y-%m-%d'))

@app.route('/add_recurring', methods=['POST'])
@login_required
def add_recurring():
    amount = float(request.form.get('amount'))
    description = request.form.get('description')
    frequency = request.form.get('frequency')
    next_due_str = request.form.get('next_due_date')
    next_due_date = datetime.strptime(next_due_str, '%Y-%m-%d')
    
    r = RecurringTransaction(
        amount=amount,
        description=description,
        frequency=frequency,
        next_due_date=next_due_date,
        type='expense',
        household_id=current_user.household_id
    )
    db.session.add(r)
    db.session.commit()
    return redirect(url_for('transactions'))

@app.route('/delete_recurring/<int:id>')
@login_required
def delete_recurring(id):
    r = RecurringTransaction.query.get_or_404(id)
    if r.household_id == current_user.household_id:
        db.session.delete(r)
        db.session.commit()
    return redirect(url_for('transactions'))

@app.route('/check_recurring')
@login_required
def check_recurring():
    recurring = RecurringTransaction.query.filter_by(household_id=current_user.household_id).all()
    today = datetime.utcnow()
    
    count = 0
    for r in recurring:
        if r.next_due_date <= today:
            t = Transaction(
                amount=r.amount,
                description=f"{r.description} (Recurring)",
                type=r.type,
                date=today,
                user_id=current_user.id,
                household_id=current_user.household_id
            )
            db.session.add(t)
            
            if r.frequency == 'weekly':
                r.next_due_date += timedelta(weeks=1)
            elif r.frequency == 'monthly':
                r.next_due_date += timedelta(days=30) 
            elif r.frequency == 'yearly':
                r.next_due_date += timedelta(days=365)
                
            count += 1
            
    db.session.commit()
    flash(f'Processed {count} recurring transactions.')
    return redirect(url_for('transactions'))

@app.route('/transactions/delete/<int:id>')
@login_required
def delete_transaction(id):
    t = Transaction.query.get_or_404(id)
    if t.household_id == current_user.household_id:
        db.session.delete(t)
        db.session.commit()
    return redirect(url_for('transactions'))

@app.route('/budgets')
@login_required
def budgets():
    categories = Category.query.filter_by(household_id=current_user.household_id).all()
    budgets = Budget.query.filter_by(household_id=current_user.household_id).all()
    
    all_transactions = Transaction.query.filter_by(household_id=current_user.household_id).all()
    total_expenses = sum(t.amount for t in all_transactions if t.type == 'expense')
    
    for b in budgets:
        spent = 0
        category_transactions = Transaction.query.filter_by(category_id=b.category_id, household_id=current_user.household_id).all()
        
        if b.category.type == 'income':
            category_income = 0
            for t in category_transactions:
                if t.type == 'income':
                    category_income += CurrencyConverter.convert(t.amount, t.currency, b.currency)
            
            total_expenses_in_budget_currency = CurrencyConverter.convert(total_expenses, current_user.household.base_currency, b.currency)
            spent = category_income - total_expenses_in_budget_currency
            
        else:
            for t in category_transactions:
                if t.type == 'expense':
                    spent += CurrencyConverter.convert(t.amount, t.currency, b.currency)
        
        b.spent = spent

    return render_template('budgets.html', budgets=budgets, categories=categories)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        base_currency = request.form.get('base_currency')
        if base_currency in ['USD', 'EUR', 'MKD']:
            current_user.household.base_currency = base_currency
            
            transactions = Transaction.query.filter_by(household_id=current_user.household_id).all()
            for t in transactions:
                t.amount_in_base_currency = CurrencyConverter.convert(t.amount, t.currency, base_currency)
            
            db.session.commit()
            flash('Settings updated successfully!', 'success')
        else:
            flash('Invalid currency selected.', 'danger')
        return redirect(url_for('settings'))
        
    return render_template('settings.html')

@app.route('/add_category', methods=['POST'])
@login_required
def add_category():
    name = request.form.get('name')
    type = request.form.get('type')
    c = Category(name=name, type=type, household_id=current_user.household_id)
    db.session.add(c)
    db.session.commit()
    flash(f'Category "{name}" added successfully!', 'success')
    return redirect(url_for('budgets'))

@app.route('/delete_category/<int:id>')
@login_required
def delete_category(id):
    c = Category.query.get_or_404(id)
    if c.household_id == current_user.household_id:
        Budget.query.filter_by(category_id=id).delete()
        db.session.delete(c)
        db.session.commit()
        flash(f'Category deleted successfully!', 'success')
    return redirect(url_for('budgets'))

@app.route('/set_budget', methods=['POST'])
@login_required
def set_budget():
    category_id = request.form.get('category_id')
    amount_limit = float(request.form.get('amount_limit'))
    currency = request.form.get('currency', 'USD')
    
    existing = Budget.query.filter_by(category_id=category_id, household_id=current_user.household_id).first()
    if existing:
        existing.amount_limit = amount_limit
        existing.currency = currency
    else:
        b = Budget(category_id=category_id, amount_limit=amount_limit, currency=currency, household_id=current_user.household_id)
        db.session.add(b)
    
    db.session.commit()
    return redirect(url_for('budgets'))

@app.route('/delete_budget/<int:id>')
@login_required
def delete_budget(id):
    b = Budget.query.get_or_404(id)
    if b.household_id == current_user.household_id:
        db.session.delete(b)
        db.session.commit()
    return redirect(url_for('budgets'))

@app.route('/accounts')
@login_required
def accounts():
    accounts = Account.query.filter_by(household_id=current_user.household_id).all()
    integrations = Integration.query.filter_by(household_id=current_user.household_id).all()
    return render_template('accounts.html', accounts=accounts, integrations=integrations)

@app.route('/add_account', methods=['POST'])
@login_required
def add_account():
    name = request.form.get('name')
    type = request.form.get('type')
    balance = float(request.form.get('balance'))
    invested_amount = float(request.form.get('invested_amount', 0.0))
    
    a = Account(name=name, type=type, balance=balance, invested_amount=invested_amount, household_id=current_user.household_id)
    db.session.commit()
    return redirect(url_for('accounts'))

@app.route('/update_invested/<int:id>', methods=['POST'])
@login_required
def update_invested(id):
    account = Account.query.get_or_404(id)
    if account.household_id == current_user.household_id:
        account.invested_amount = float(request.form.get('invested_amount'))
        db.session.commit()
    return redirect(url_for('accounts'))

@app.route('/add_integration', methods=['POST'])
@login_required
def add_integration():
    platform = request.form.get('platform')
    api_key = request.form.get('api_key')
    api_secret = request.form.get('api_secret')
    
    i = Integration(platform=platform, api_key=api_key, api_secret=api_secret, household_id=current_user.household_id)
    db.session.add(i)
    db.session.commit()
    return redirect(url_for('accounts'))

@app.route('/delete_integration/<int:id>')
@login_required
def delete_integration(id):
    i = Integration.query.get_or_404(id)
    if i.household_id == current_user.household_id:
        db.session.delete(i)
        db.session.commit()
    return redirect(url_for('accounts'))

@app.route('/sync_integrations')
@login_required
def sync_integrations():
    sync_integrations_helper(current_user.household_id)
    flash('Integrations synced successfully!', 'success')
    return redirect(url_for('accounts'))

@app.route('/api/history')
@login_required
def api_history():
    time_range = request.args.get('range', 'all')
    resolution = request.args.get('resolution', 'daily')
    
    now = datetime.utcnow()
    start_date = None
    
    if time_range == '7d':
        start_date = now - timedelta(days=7)
    elif time_range == '30d':
        start_date = now - timedelta(days=30)
    elif time_range == '3m':
        start_date = now - timedelta(days=90)
    elif time_range == '1y':
        start_date = now - timedelta(days=365)

    accounts = Account.query.filter_by(household_id=current_user.household_id).all()
    
    history = BalanceHistory.query.join(Account).filter(
        Account.household_id == current_user.household_id
    ).order_by(BalanceHistory.date).all()
    
    if not history:
        return jsonify({'datasets': [], 'labels': []})
        
    if not start_date:
        start_date = history[0].date

    target_dates = []
    current_date = start_date
    
    if resolution == 'daily':
        current_date = current_date.replace(hour=23, minute=59, second=59)
    elif resolution == 'weekly':
        days_ahead = 6 - current_date.weekday()
        current_date = current_date + timedelta(days=days_ahead)
        current_date = current_date.replace(hour=23, minute=59, second=59)
    
    while current_date <= now:
        target_dates.append(current_date)
        if resolution == 'daily':
            current_date += timedelta(days=1)
        elif resolution == 'weekly':
            current_date += timedelta(weeks=1)
        elif resolution == 'monthly':
            current_date += timedelta(days=30) 
    
    if not target_dates or target_dates[-1] < now:
        target_dates.append(now)

    from collections import defaultdict
    account_history = defaultdict(list)
    for h in history:
        account_history[h.account_id].append(h)

    datasets = []
    labels = [d.strftime('%Y-%m-%d') for d in target_dates]
    
    for acc in accounts:
        acc_history = account_history.get(acc.id, [])
        balances = []
        invested_amounts = []
        
        for target_date in target_dates:
            last_record = None
            for h in acc_history:
                if h.date <= target_date:
                    last_record = h
                else:
                    break
            
            if last_record:
                balances.append(last_record.balance)
                invested_amounts.append(last_record.invested_amount)
            else:
                balances.append(0)
                invested_amounts.append(0)
        
        datasets.append({
            'label': f'{acc.name} (Current)',
            'data': balances,
            'type': 'balance',
            'borderColor': 'var(--accent-color)',
            'fill': False,
            'tension': 0.4
        })
        
        if any(invested_amounts):
            datasets.append({
                'label': f'{acc.name} (Invested)',
                'data': invested_amounts,
                'type': 'invested',
                'borderDash': [5, 5],
                'fill': False,
                'tension': 0.4
            })

    return jsonify({'datasets': datasets, 'labels': labels})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
