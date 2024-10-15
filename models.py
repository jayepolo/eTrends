from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

class Vendor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    town = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    prices = db.relationship('PriceData', back_populates='vendor')

class PriceData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor.id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    vendor = db.relationship('Vendor', back_populates='prices')

    __table_args__ = (
        db.Index('idx_price_date', 'date'),
        db.Index('idx_price_vendor', 'vendor_id'),
    )

class FederalPriceData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    price = db.Column(db.Float, nullable=False)

class ScrapeLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    success = db.Column(db.Boolean, nullable=False)
    message = db.Column(db.Text)
    scheduled = db.Column(db.Boolean, nullable=False)
    scrape_type = db.Column(db.String(10), nullable=False)  # 'Local' or 'Federal'