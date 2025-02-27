# models.py
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100))
    grade = db.Column(db.String(10), default='user')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Ebook(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255))
    isbn = db.Column(db.String(50))
    publish_date = db.Column(db.Date)
    file_format = db.Column(db.String(10), nullable=False)
    file_data = db.Column(db.LargeBinary, nullable=False)
    summary = db.Column(db.Text)
    created_date = db.Column(db.Date, default=datetime.utcnow)
    updated_date = db.Column(db.Date, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    ebook_metadata = db.relationship('Metadata', backref='ebook', cascade='all, delete-orphan')

class Metadata(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ebook_id = db.Column(db.Integer, db.ForeignKey('ebook.id'))
    tag = db.Column(db.String(255))
    value = db.Column(db.Text)

class Logging(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    table_name = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text)

    def __repr__(self):
        return f"<Logging {self.table_name} {self.action} by User {self.user_id} at {self.timestamp}>"