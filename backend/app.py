import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from models import db, User, Task, Comment, GroupLeader
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'super-secret'  

# SMTP configuration
SMTP_HOST = 'smtp.elasticemail.com'
SMTP_PORT = 2525
SMTP_USERNAME = 'onsasebravin853@gmail.com'
SMTP_PASSWORD = 'C00CDC762A095AE842C3D13FBE7A2AA99E52'
SMTP_SENDER_EMAIL = 'onsasebravin853@gmail.com'

db.init_app(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
CORS(app)


@app.route('/email-notification', methods=['POST'])
@jwt_required()  # Ensure the request is authenticated
def email_notification():
    try:
        # Get the current user ID
        current_user_id = get_jwt_identity()

        # Get the user from the database
        user = User.query.get(current_user_id)
        if not user:
            return jsonify({'message': 'User not found'}), 404

        # Check if the user has opted in for email notifications
        if not user.email_notification_enabled:
            return jsonify({'message': 'Email notifications are not enabled for this user'}), 400

        # Get the tasks nearing their deadlines for the user
        approaching_tasks = []
        today = datetime.utcnow()
        deadline_threshold = today + timedelta(days=1)  # Consider tasks with deadline within 24 hours
        for task in user.tasks:
            if not task.completed and task.deadline <= deadline_threshold:
                approaching_tasks.append(task)

        # Send email notifications for approaching tasks
        smtp_server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        smtp_server.starttls()
        smtp_server.login(SMTP_USERNAME, SMTP_PASSWORD)

        for task in approaching_tasks:
            msg = MIMEMultipart()
            msg['From'] = SMTP_SENDER_EMAIL
            msg['To'] = user.email
            msg['Subject'] = 'Task Deadline Notification'
            task_title = task.title
            deadline_date = task.deadline.strftime('%Y-%m-%d')
            body = f"This is a notification email to remind you of an approaching task deadline.\n\nTask: {task_title}\nDeadline: {deadline_date}"
            msg.attach(MIMEText(body, 'plain'))
            smtp_server.send_message(msg)

        smtp_server.quit()

        return jsonify({'message': 'Email notifications sent successfully'}), 200
    except Exception as e:
        return jsonify({'message': f'Failed to send email notifications: {str(e)}'}), 500

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
    progress = min(int(data.get('progress', 0)), 100)  # Default progress is 0
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
@jwt_required()
def get_user_tasks():
    user_id = get_jwt_identity()  # Get the ID of the authenticated user

    # Query all tasks associated with the authenticated user
    user_tasks = Task.query.filter_by(user_id=user_id).paginate(page=request.args.get('page', 1, type=int), per_page=5)

    # Construct a list of task data
    tasks_data = []
    for task in user_tasks.items:
        # Get user information including group leader
        user = task.user

        # Construct task comments data
        task_comments = [{'id': comment.id, 'text': comment.text, 'created_at': comment.created_at, 'user_id': comment.user_id} for comment in task.comments]

        # Construct task data including user and group leader information
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
            'group_leader_id': None,  # Default to None
            'comments': task_comments
        }

        # If user has a group leader, add group leader ID to task data
        if user.group_leader:
            task_data['group_leader_id'] = user.group_leader_id

        tasks_data.append(task_data)

    return jsonify({'tasks': tasks_data, 'total_tasks': user_tasks.total, 'current_page': user_tasks.page, 'per_page': user_tasks.per_page}), 200

@app.route('/tasks/<int:task_id>', methods=['GET'])
@jwt_required()
def get_task_by_id_endpoint(task_id):
    user_id = get_jwt_identity()  # Get the ID of the authenticated user

    # Query the task by ID and user ID
    task = Task.query.filter_by(id=task_id, user_id=user_id).first_or_404()

    # Get user information including group leader
    user = task.user

    # Construct task comments data
    task_comments = [{'id': comment.id, 'text': comment.text, 'created_at': comment.created_at, 'user_id': comment.user_id} for comment in task.comments]

    # Construct task data including user and group leader information
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
        'group_leader_id': None,  # Default to None
        'comments': task_comments
    }

    # If user has a group leader, add group leader ID to task data
    if user.group_leader:
        task_data['group_leader_id'] = user.group_leader_id

    return jsonify({'task': task_data}), 200

# Update a task
@app.route('/tasks/<int:task_id>', methods=['PATCH'])
@jwt_required()
def update_task(task_id):
    user_id = get_jwt_identity()
    task = Task.query.filter_by(id=task_id, user_id=user_id).first()
    if not task:
        return jsonify({'message': 'Task not found'}), 404

    data = request.json
    title = data.get('title')
    description = data.get('description')
    deadline_str = data.get('deadline')
    progress = min(int(data.get('progress', 0)), 100)
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
    user_id = get_jwt_identity()
    task = Task.query.filter_by(id=task_id, user_id=user_id).first()
    if not task:
        return jsonify({'message': 'Task not found'}), 404

    # Delete associated comments
    Comment.query.filter_by(task_id=task_id).delete()

    # Delete the task
    db.session.delete(task)
    db.session.commit()

    return jsonify({'message': 'Task and associated comments deleted successfully'}), 200


@app.route('/all-tasks', methods=['GET'])
def get_all_tasks():
    tasks = Task.query.paginate(page=request.args.get('page', 1, type=int), per_page=5)

    tasks_data = []
    for task in tasks.items:
        # Get user information including group leader
        user = task.user

        # Construct task comments data
        task_comments = [{'id': comment.id, 'text': comment.text, 'created_at': comment.created_at, 'user_id': comment.user_id} for comment in task.comments]

        # Construct task data including user and group leader information
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
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'profile_image': user.profile_image
            },
            'group_leader': None,  # Default to None
            'comments': task_comments  # Add comments data
        }
        tasks_data.append(task_data)

    return jsonify({'tasks': tasks_data, 'total_tasks': tasks.total, 'current_page': tasks.page, 'per_page': tasks.per_page}), 200



@app.route('/all-tasks/<int:task_id>', methods=['GET'])
def get_task_by_id(task_id):
    # Query the task by ID
    task = Task.query.get_or_404(task_id)

    # Get user information including group leader
    user = task.user

    # Construct task comments data
    task_comments = [{'id': comment.id, 'text': comment.text, 'created_at': comment.created_at, 'user_id': comment.user_id} for comment in task.comments]

    # Construct task data including user and group leader information
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
        'group_leader_id': None,  # Default to None
        'comments': task_comments
    }

    # If user has a group leader, add group leader ID to task data
    if user.group_leader:
        task_data['group_leader_id'] = user.group_leader_id

    return jsonify({'task': task_data}), 200

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

    # Ensure that the user can only update their own profile
    if username and user.username != username:
        return jsonify({'message': 'You are not authorized to update this profile'}), 403

    if profile_image:
        user.profile_image = profile_image

    db.session.commit()

    return jsonify({'message': 'User profile updated successfully'}), 200

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

    # Create a new GroupLeader instance with the user's information
    group_leader = GroupLeader(username=user.username, email=user.email, password=user.password, profile_image=user.profile_image)
    db.session.add(group_leader)

    # Assign the new GroupLeader to the user
    user.group_leader = group_leader

    # Commit the changes to the database
    db.session.commit()

    return jsonify({'message': 'User promoted to group leader'}), 200


# When creating a comment
@app.route('/comments', methods=['POST'])
@jwt_required()
def create_comment():
    user_id = get_jwt_identity()  # Get the ID of the authenticated user
    data = request.get_json()

    # Create the comment and associate it with the user ID
    comment = Comment(text=data['text'], user_id=user_id, task_id=data['task_id'])
    db.session.add(comment)
    db.session.commit()

    return jsonify({'message': 'Comment created successfully'}), 201


# When deleting a comment
@app.route('/comments/<int:comment_id>', methods=['DELETE'])
@jwt_required()
def delete_comment(comment_id):
    user_id = get_jwt_identity()  # Get the ID of the authenticated user

    # Query the comment by ID
    comment = Comment.query.get_or_404(comment_id)

    # Check if the authenticated user is the owner of the comment
    if comment.user_id != user_id:
        return jsonify({'error': 'You are not authorized to delete this comment'}), 403

    # Delete the comment
    db.session.delete(comment)
    db.session.commit()

    return jsonify({'message': 'Comment deleted successfully'}), 200

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


# Edit a task assigned by a group leader to a user
@app.route('/group_leaders/<int:group_leader_id>/users/<int:user_id>/tasks/<int:task_id>', methods=['PATCH'])
@jwt_required()
def edit_task_assigned_by_group_leader(group_leader_id, user_id, task_id):
    data = request.json

    # Check if the user belongs to the group leader
    user = User.query.get(user_id)
    if not user or user.group_leader_id != group_leader_id:
        return jsonify({'message': 'User not found or does not belong to this group leader'}), 404

    # Get the task
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'message': 'Task not found'}), 404

    # Update task attributes
    if 'title' in data:
        task.title = data['title']
    if 'description' in data:
        task.description = data['description']
    if 'deadline' in data:
        try:
            deadline = datetime.strptime(data['deadline'], '%Y-%m-%d')
        except ValueError:
            return jsonify({'message': 'Invalid deadline format. Use YYYY-MM-DD'}), 400
        task.deadline = deadline
    if 'progress' in data:
        task.progress = min(data['progress'], 100)
    if 'priority' in data:
        task.priority = data['priority']
    if 'completed' in data:
        task.completed = data['completed']

    db.session.commit()

    return jsonify({'message': 'Task updated successfully'}), 200

# Delete a task assigned by a group leader to a user
@app.route('/group_leaders/<int:group_leader_id>/users/<int:user_id>/tasks/<int:task_id>', methods=['DELETE'])
@jwt_required()
def delete_task_assigned_by_group_leader(group_leader_id, user_id, task_id):
    # Check if the user belongs to the group leader
    user = User.query.get(user_id)
    if not user or user.group_leader_id != group_leader_id:
        return jsonify({'message': 'User not found or does not belong to this group leader'}), 404

    # Get the task
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'message': 'Task not found'}), 404

    # Delete associated comments first
    Comment.query.filter_by(task_id=task_id).delete()

    # Delete the task
    db.session.delete(task)
    db.session.commit()

    return jsonify({'message': 'Task deleted successfully'}), 200


# Get users assigned by a group leader
@app.route('/group_leaders/<int:group_leader_id>/users', methods=['GET'])
@jwt_required()
def get_users_assigned_by_group_leader(group_leader_id):
    # Get users assigned by the group leader
    users = User.query.filter_by(group_leader_id=group_leader_id).all()
    users_data = [{'id': user.id, 'username': user.username, 'email': user.email, 'profile_image': user.profile_image} for user in users]

    return jsonify({'users': users_data}), 200

# Get tasks assigned by a group leader to all users
@app.route('/group_leaders/<int:group_leader_id>/tasks', methods=['GET'])
@jwt_required()
def get_tasks_assigned_by_group_leader(group_leader_id):
    # Get tasks assigned by the group leader to all users
    tasks = Task.query.join(User).filter(User.group_leader_id == group_leader_id).all()
    tasks_data = [{'id': task.id, 'title': task.title, 'description': task.description, 'deadline': task.deadline, 'progress': task.progress, 'priority': task.priority, 'completed': task.completed, 'created_at': task.created_at} for task in tasks]

    return jsonify({'tasks': tasks_data}), 200


# Update a group leader (demote to normal user)
@app.route('/group_leaders/<int:group_leader_id>', methods=['PATCH'])
@jwt_required()
def update_group_leader(group_leader_id):
    group_leader = GroupLeader.query.get(group_leader_id)
    if not group_leader:
        return jsonify({'message': 'Group leader not found'}), 404

    # Update the group leader to a normal user by removing them from the GroupLeader table
    user = User.query.filter_by(group_leader_id=group_leader_id).first()
    if user:
        user.group_leader_id = None  # Remove the group leader association
        db.session.commit()

    db.session.delete(group_leader)  # Remove them as a group leader
    db.session.commit()

    return jsonify({'message': 'Group leader demoted to normal user'}), 200

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

# Get all users
@app.route('/users', methods=['GET'])
def get_all_users():
    users = User.query.all()
    users_data = [{'id': user.id, 'username': user.username, 'email': user.email, 'profile_image': user.profile_image} for user in users]

    return jsonify({'users': users_data}), 200

# Get all comments
@app.route('/comments', methods=['GET'])
def get_all_comments():
    comments = Comment.query.all()
    comments_data = [{'id': comment.id, 'text': comment.text, 'created_at': comment.created_at, 'user_id': comment.user_id, 'task_id': comment.task_id} for comment in comments]

    return jsonify({'comments': comments_data}), 200

# Get user by ID
@app.route('/users/<int:user_id>', methods=['GET'])
def get_user_by_id(user_id):
    user = User.query.get_or_404(user_id)
    user_data = {'id': user.id, 'username': user.username, 'email': user.email, 'profile_image': user.profile_image}
    return jsonify({'user': user_data}), 200

# Get comment by ID
@app.route('/comments/<int:comment_id>', methods=['GET'])
def get_comment_by_id(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    comment_data = {'id': comment.id, 'text': comment.text, 'created_at': comment.created_at, 'user_id': comment.user_id, 'task_id': comment.task_id}
    return jsonify({'comment': comment_data}), 200

# Get all group leaders with detailed information
@app.route('/group_leaders', methods=['GET'])
@jwt_required()
def get_all_group_leaders():
    group_leaders = GroupLeader.query.all()
    group_leaders_data = []

    for group_leader in group_leaders:
        # Retrieve group leader's associated users
        users = group_leader.users
        users_data = [{'id': user.id, 'username': user.username, 'email': user.email, 'profile_image': user.profile_image} for user in users]
        
        # Retrieve group leader's assigned tasks
        tasks = group_leader.tasks
        tasks_data = [{'id': task.id, 'title': task.title, 'description': task.description, 'deadline': task.deadline, 'progress': task.progress, 'priority': task.priority, 'completed': task.completed, 'created_at': task.created_at} for task in tasks]

        group_leader_data = {
            'id': group_leader.id,
            'users': users_data,
            'tasks': tasks_data
        }
        
        group_leaders_data.append(group_leader_data)

    return jsonify({'group_leaders': group_leaders_data}), 200

# Get group leader by ID with detailed information
@app.route('/group_leaders/<int:group_leader_id>', methods=['GET'])
@jwt_required()
def get_group_leader_by_id(group_leader_id):
    group_leader = GroupLeader.query.get_or_404(group_leader_id)
    
    # Retrieve group leader's associated users
    users = group_leader.users
    users_data = [{'id': user.id, 'username': user.username, 'email': user.email, 'profile_image': user.profile_image} for user in users]
    
    # Retrieve group leader's assigned tasks
    tasks = group_leader.tasks
    tasks_data = [{'id': task.id, 'title': task.title, 'description': task.description, 'deadline': task.deadline, 'progress': task.progress, 'priority': task.priority, 'completed': task.completed, 'created_at': task.created_at} for task in tasks]
    
    group_leader_data = {
        'id': group_leader.id,
        'users': users_data,
        'tasks': tasks_data
    }
    
    return jsonify({'group_leader': group_leader_data}), 200

# Logout (delete session)
@app.route('/logout', methods=['DELETE'])
@jwt_required()
def logout():
    return jsonify({'message': 'Logged out successfully'}), 200

@app.route('/delete_account', methods=['DELETE'])
@jwt_required()
def delete_account():
    current_user_id = get_jwt_identity()

    # Delete the user from the database
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    db.session.delete(user)
    db.session.commit()

    return jsonify({'message': 'Account deleted successfully'}), 200

if __name__ == '__main__':
    # Create all database tables
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5552)

