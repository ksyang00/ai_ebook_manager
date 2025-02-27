# app.py
from flask import Flask
from models import db
from routes import app
from events import log_changes

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)