from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from models import db, User, Task, Comment, GroupLeader
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'super-secret'

db.init_app(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
CORS(app)

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    profile_image = data.get('profile_image')  # Optional

    if not username or not email or not password:
        return jsonify({'message': 'Username, email, and password are required'}), 400

    # Check if the email is already registered
    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'Email already exists'}), 400

    # Hash the password
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    # Create the user
    user = User(username=username, email=email, password=hashed_password, profile_image=profile_image)
    db.session.add(user)
    db.session.commit()

    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()

    if not user or not bcrypt.check_password_hash(user.password, password):
        return jsonify({'message': 'Invalid email or password'}), 401

    access_token = create_access_token(identity=user.id)
    return jsonify({'access_token': access_token}), 200

# Create a task
@app.route('/tasks', methods=['POST'])
@jwt_required()
def create_task():
    data = request.json
    title = data.get('title')
    description = data.get('description')
    deadline_str = data.get('deadline')
    progress = data.get('progress', 0)  # Default progress is 0
    priority = data.get('priority', 'normal')  # Default priority is 'normal'
    user_id = get_jwt_identity()

    if not title or not description or not deadline_str:
        return jsonify({'message': 'Title, description, and deadline are required'}), 400

    try:
        deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'message': 'Invalid deadline format. Use YYYY-MM-DD'}), 400

    # Set the default value of completed as False (no)
    completed = False

    task = Task(title=title, description=description, deadline=deadline, progress=progress, priority=priority, completed=completed, user_id=user_id)
    db.session.add(task)
    db.session.commit()

    return jsonify({'message': 'Task created successfully', 'task': {'id': task.id, 'title': task.title, 'description': task.description, 'deadline': task.deadline, 'progress': task.progress, 'priority': task.priority, 'completed': task.completed, 'created_at': task.created_at}}), 201

@app.route('/tasks', methods=['GET'])
def get_all_tasks():
    tasks = Task.query.all()
    tasks_data = []

    for task in tasks:
        task_comments = [{'id': comment.id, 'text': comment.text, 'created_at': comment.created_at, 'user_id': comment.user_id} for comment in task.comments]
        task_data = {
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'created_at': task.created_at,
            'deadline': task.deadline,
            'progress': task.progress,
            'priority': task.priority,
            'completed': task.completed,
            'user_id': task.user_id,
            'group_leader_id': task.group_leader_id,  # Include group_leader_id here
            'comments': task_comments
        }
        tasks_data.append(task_data)

    return jsonify({'tasks': tasks_data}), 200

@app.route('/tasks/<int:task_id>', methods=['GET'])
def get_task_by_id(task_id):
    task = Task.query.get_or_404(task_id)
    task_comments = [{'id': comment.id, 'text': comment.text, 'created_at': comment.created_at, 'user_id': comment.user_id} for comment in task.comments]
    task_data = {
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'created_at': task.created_at,
        'deadline': task.deadline,
        'progress': task.progress,
        'priority': task.priority,
        'completed': task.completed,
        'user_id': task.user_id,
        'group_leader_id': task.group_leader_id,  # Include group_leader_id here
        'comments': task_comments
    }
    
    return jsonify({'task': task_data}), 200


# Update a task
@app.route('/tasks/<int:task_id>', methods=['PATCH'])
@jwt_required()
def update_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'message': 'Task not found'}), 404

    data = request.json
    title = data.get('title')
    description = data.get('description')
    deadline_str = data.get('deadline')
    progress = data.get('progress')
    priority = data.get('priority')

    if title:
        task.title = title
    if description:
        task.description = description
    if deadline_str:
        try:
            task.deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'message': 'Invalid deadline format. Use YYYY-MM-DD'}), 400
    if progress is not None:
        task.progress = progress
    if priority:
        task.priority = priority

    # Don't forget to set completed to False if it's not provided in the request
    task.completed = data.get('completed', False)

    db.session.commit()

    return jsonify({'message': 'Task updated successfully'}), 200

# Delete a task
@app.route('/tasks/<int:task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'message': 'Task not found'}), 404

    db.session.delete(task)
    db.session.commit()

    return jsonify({'message': 'Task deleted successfully'}), 200

# Get user profile
@app.route('/users/profile', methods=['GET'])
@jwt_required()
def get_user_profile():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    return jsonify({'username': user.username, 'email': user.email, 'profile_image': user.profile_image}), 200

# Update user profile
@app.route('/users/profile', methods=['PATCH'])
@jwt_required()
def update_user_profile():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    data = request.json
    username = data.get('username')
    profile_image = data.get('profile_image')

    if username:
        user.username = username
    if profile_image:
        user.profile_image = profile_image

    db.session.commit()

    return jsonify({'message': 'User profile updated successfully'}), 200

# Create a comment
@app.route('/comments', methods=['POST'])
@jwt_required()
def create_comment():
    data = request.json
    text = data.get('text')
    task_id = data.get('task_id')
    user_id = get_jwt_identity()

    if not text or not task_id:
        return jsonify({'message': 'Text and task_id are required'}), 400

    comment = Comment(text=text, task_id=task_id, user_id=user_id)
    db.session.add(comment)
    db.session.commit()

    return jsonify({'message': 'Comment created successfully', 'comment_id': comment.id}), 201

# Update a comment
@app.route('/comments/<int:comment_id>', methods=['PATCH'])
@jwt_required()
def update_comment(comment_id):
    data = request.json
    text = data.get('text')

    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({'message': 'Comment not found'}), 404

    comment.text = text
    db.session.commit()

    return jsonify({'message': 'Comment updated successfully'}), 200

# Delete a comment
@app.route('/comments/<int:comment_id>', methods=['DELETE'])
@jwt_required()
def delete_comment(comment_id):
    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({'message': 'Comment not found'}), 404

    db.session.delete(comment)
    db.session.commit()

    return jsonify({'message': 'Comment deleted successfully'}), 200

# Promote a user to group leader
@app.route('/users/<int:user_id>/promote', methods=['PATCH'])
@jwt_required()
def promote_to_group_leader(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    # Check if the user is already a group leader
    if user.group_leader_id is not None:
        return jsonify({'message': 'User is already a group leader'}), 400

    # Promote the user to group leader
    group_leader = GroupLeader()
    user.group_leader = group_leader
    db.session.commit()

    return jsonify({'message': 'User promoted to group leader'}), 200

# Assign multiple users to a group leader
@app.route('/group_leaders/<int:group_leader_id>/assign_users', methods=['POST'])
@jwt_required()
def assign_users_to_group_leader(group_leader_id):
    data = request.json
    user_ids = data.get('user_ids', [])

    # Check if the group leader exists
    group_leader = GroupLeader.query.get(group_leader_id)
    if not group_leader:
        return jsonify({'message': 'Group leader not found'}), 404

    # Assign users to the group leader
    for user_id in user_ids:
        user = User.query.get(user_id)
        if user:
            user.group_leader_id = group_leader_id
        else:
            return jsonify({'message': f'User with ID {user_id} not found'}), 404

    db.session.commit()

    return jsonify({'message': 'Users assigned to group leader successfully'}), 200

# Assign multiple tasks to a user under a group leader
@app.route('/group_leaders/<int:group_leader_id>/users/<int:user_id>/assign_tasks', methods=['POST'])
@jwt_required()
def group_leader_assign_tasks_to_user(group_leader_id, user_id):
    # Check if the user is a group leader
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user or current_user.group_leader_id != group_leader_id:
        return jsonify({'message': 'Access denied. You are not authorized to perform this action.'}), 403

    data = request.json
    task_ids = data.get('task_ids', [])

    # Check if the user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    # Assign tasks to the user
    for task_id in task_ids:
        task = Task.query.get(task_id)
        if task:
            task.user_id = user_id
        else:
            return jsonify({'message': f'Task with ID {task_id} not found'}), 404

    db.session.commit()

    return jsonify({'message': 'Tasks assigned to user successfully'}), 200

# Get tasks assigned to users by a group leader
@app.route('/group_leaders/<int:group_leader_id>/users/<int:user_id>/tasks', methods=['GET'])
@jwt_required()
def group_leader_get_tasks_assigned_to_user(group_leader_id, user_id):
    # Check if the user belongs to the group leader
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user or current_user.group_leader_id != group_leader_id:
        return jsonify({'message': 'Access denied. You are not authorized to perform this action.'}), 403

    # Check if the specified user belongs to the group leader
    user = User.query.get(user_id)
    if not user or user.group_leader_id != group_leader_id:
        return jsonify({'message': 'User not found or does not belong to this group leader'}), 404

    # Get tasks assigned to the user
    tasks = user.assigned_tasks
    tasks_data = []

    for task in tasks:
        # Get comments for the task
        task_comments = [{'id': comment.id, 'text': comment.text, 'created_at': comment.created_at, 'user_id': comment.user_id} for comment in task.comments]

        task_data = {
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'deadline': task.deadline,
            'progress': task.progress,
            'priority': task.priority,
            'completed': task.completed,
            'created_at': task.created_at,
            'comments': task_comments  # Include comments for the task
        }
        tasks_data.append(task_data)

    return jsonify({'tasks': tasks_data}), 200

# Get tasks by Id assigned to users by a group leader
@app.route('/group_leaders/<int:group_leader_id>/users/<int:user_id>/tasks/<int:task_id>', methods=['GET'])
@jwt_required()
def group_leader_get_task_by_id(group_leader_id, user_id, task_id):
    # Check if the user making the request is authenticated and belongs to the specified group leader
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user or current_user.group_leader_id != group_leader_id:
        return jsonify({'message': 'Access denied. You are not authorized to perform this action.'}), 403

    # Check if the specified user belongs to the specified group leader
    user = User.query.get(user_id)
    if not user or user.group_leader_id != group_leader_id:
        return jsonify({'message': 'User not found or does not belong to this group leader'}), 404

    # Retrieve the task assigned to the specified user by its ID
    task = Task.query.filter_by(id=task_id, user_id=user_id).first()
    if not task:
        return jsonify({'message': 'Task not found for the specified user'}), 404

    # Retrieve comments associated with the task
    comments = task.comments
    comments_data = [{'id': comment.id, 'text': comment.text, 'created_at': comment.created_at, 'user_id': comment.user_id} for comment in comments]

    # Serialize the task data along with comments and return it in the response
    task_data = {
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'deadline': task.deadline,
        'progress': task.progress,
        'priority': task.priority,
        'completed': task.completed,
        'created_at': task.created_at,
        'comments': comments_data  # Include comments in the task data
    }
    return jsonify({'task': task_data}), 200
