from flask_login import UserMixin
from datetime import datetime
from extensions import db

class Household(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    join_code = db.Column(db.String(20), unique=True, nullable=False)
    base_currency = db.Column(db.String(3), default='USD', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    users = db.relationship('User', backref='household', lazy=True)
    accounts = db.relationship('Account', backref='household', lazy=True)
    integrations = db.relationship('Integration', backref='household', lazy=True)
    transactions = db.relationship('Transaction', backref='household', lazy=True)
    recurring_transactions = db.relationship('RecurringTransaction', backref='household', lazy=True)
    categories = db.relationship('Category', backref='household', lazy=True)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=True)

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False) # 'Cash', 'Investment'
    balance = db.Column(db.Float, default=0.0)
    invested_amount = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(10), default='USD')
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
    history = db.relationship('BalanceHistory', backref='account', lazy=True)

class BalanceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    balance = db.Column(db.Float, nullable=False)
    invested_amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

class Integration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(50), nullable=False) # 'bybit', 'trading212'
    api_key = db.Column(db.String(200), nullable=True)
    api_secret = db.Column(db.String(200), nullable=True)
    last_synced = db.Column(db.DateTime, default=None, nullable=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(20), nullable=False) # 'expense', 'income', 'savings'
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
    budgets = db.relationship('Budget', backref='category', lazy=True)
    transactions = db.relationship('Transaction', backref='category', lazy=True)

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    amount_limit = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='USD', nullable=False)
    period = db.Column(db.String(20), default='monthly')
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='USD', nullable=False)
    amount_in_base_currency = db.Column(db.Float, nullable=False, default=0.0)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    type = db.Column(db.String(20), nullable=False) # 'income', 'expense'
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)

class RecurringTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='USD', nullable=False)
    description = db.Column(db.String(200))
    frequency = db.Column(db.String(20), nullable=False) # 'weekly', 'monthly', 'yearly'
    next_due_date = db.Column(db.DateTime, nullable=False)
    type = db.Column(db.String(20), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
