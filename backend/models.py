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

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    deadline = db.Column(db.DateTime, nullable=False)
    progress = db.Column(db.Integer, nullable=False, default=0)
    priority = db.Column(db.String(20), nullable=False, default='Low')
    completed = db.Column(db.Boolean, nullable=False, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_leader_id = db.Column(db.Integer, db.ForeignKey('group_leader.id'))  # Add this line
    users = db.relationship('User', backref='assigned_tasks', lazy=True)
    
    comments = db.relationship('Comment', backref='task', lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

class GroupLeader(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tasks = db.relationship('Task', backref='group_leader', lazy=True)
    users = db.relationship('User', backref='group_leader', lazy=True, foreign_keys='User.group_leader_id')
    # Add a relationship back to Task
    group_tasks = db.relationship('Task', backref='group_leader_assigned', lazy=True, foreign_keys='Task.group_leader_id')
