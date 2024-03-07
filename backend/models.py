from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    profile_image = db.Column(db.String(100))
    group_leader_id = db.Column(db.Integer, db.ForeignKey('group_leader.id'))

    tasks = db.relationship('Task', backref='user', lazy=True)
    comments = db.relationship('Comment', backref='user', lazy=True)
