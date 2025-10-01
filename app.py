from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from dotenv import load_dotenv
import os
import secrets
import string
from datetime import datetime, timedelta
import schedule
import time
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import requests

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///chores.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# Initialize extensions
db = SQLAlchemy(app)
CORS(app, origins=os.getenv('CORS_ORIGINS', 'http://localhost:8081').split(','))

# Models
class Household(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(8), unique=True, nullable=False)
    rotation_mode = db.Column(db.String(20), default='weekly')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'rotation_mode': self.rotation_mode,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    household = db.relationship('Household', backref=db.backref('members', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'is_admin': self.is_admin,
            'household_id': self.household_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Chore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    days = db.Column(db.JSON, nullable=False)  # Store as JSON array
    assigned_to = db.Column(db.String(100))
    completed = db.Column(db.Boolean, default=False)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    household = db.relationship('Household', backref=db.backref('chores', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'days': self.days,
            'assigned_to': self.assigned_to,
            'completed': self.completed,
            'household_id': self.household_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_name = db.Column(db.String(100), nullable=False)
    chore_title = db.Column(db.String(200), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)  # 'reminder', 'overdue', 'rotation'
    message = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
    chore_id = db.Column(db.Integer, db.ForeignKey('chore.id'), nullable=True)

    household = db.relationship('Household', backref=db.backref('notifications', lazy=True))
    chore = db.relationship('Chore', backref=db.backref('notifications', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'member_name': self.member_name,
            'chore_title': self.chore_title,
            'notification_type': self.notification_type,
            'message': self.message,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'household_id': self.household_id,
            'chore_id': self.chore_id
        }

class RotationHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
    chore_id = db.Column(db.Integer, db.ForeignKey('chore.id'), nullable=False)
    previous_assigned_to = db.Column(db.String(100))
    new_assigned_to = db.Column(db.String(100))
    rotation_date = db.Column(db.DateTime, default=db.func.current_timestamp())
    rotation_type = db.Column(db.String(20), nullable=False)  # 'weekly', 'biweekly', 'monthly'

    household = db.relationship('Household', backref=db.backref('rotation_history', lazy=True))
    chore = db.relationship('Chore', backref=db.backref('rotation_history', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'household_id': self.household_id,
            'chore_id': self.chore_id,
            'previous_assigned_to': self.previous_assigned_to,
            'new_assigned_to': self.new_assigned_to,
            'rotation_date': self.rotation_date.isoformat() if self.rotation_date else None,
            'rotation_type': self.rotation_type
        }

class MemberPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_name = db.Column(db.String(100), nullable=False)
    household_id = db.Column(db.Integer, db.ForeignKey('household.id'), nullable=False)
    email = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    notification_enabled = db.Column(db.Boolean, default=True)
    reminder_time = db.Column(db.String(10), default="09:00")  # HH:MM format
    reminder_days_before = db.Column(db.Integer, default=1)

    household = db.relationship('Household', backref=db.backref('member_preferences', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'member_name': self.member_name,
            'household_id': self.household_id,
            'email': self.email,
            'phone': self.phone,
            'notification_enabled': self.notification_enabled,
            'reminder_time': self.reminder_time,
            'reminder_days_before': self.reminder_days_before
        }

def generate_household_code():
    """Generate a unique 8-character household code"""
    while True:
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        if not Household.query.filter_by(code=code).first():
            return code

# Notification Service
class NotificationService:
    @staticmethod
    def send_email_notification(to_email, subject, message):
        """Send email notification"""
        try:
            smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
            smtp_port = int(os.getenv('SMTP_PORT', '587'))
            smtp_username = os.getenv('SMTP_USERNAME')
            smtp_password = os.getenv('SMTP_PASSWORD')
            
            if not smtp_username or not smtp_password:
                print(f"Email notification skipped - SMTP not configured")
                return False
                
            msg = MIMEMultipart()
            msg['From'] = smtp_username
            msg['To'] = to_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(message, 'plain'))
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_username, smtp_password)
            text = msg.as_string()
            server.sendmail(smtp_username, to_email, text)
            server.quit()
            
            print(f"Email sent to {to_email}")
            return True
            
        except Exception as e:
            print(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    @staticmethod
    def send_sms_notification(phone_number, message):
        """Send SMS notification using Twilio"""
        try:
            account_sid = os.getenv('TWILIO_ACCOUNT_SID')
            auth_token = os.getenv('TWILIO_AUTH_TOKEN')
            twilio_phone = os.getenv('TWILIO_PHONE_NUMBER')
            
            if not all([account_sid, auth_token, twilio_phone]):
                print(f"SMS notification skipped - Twilio not configured")
                return False
                
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            
            message = client.messages.create(
                body=message,
                from_=twilio_phone,
                to=phone_number
            )
            
            print(f"SMS sent to {phone_number}")
            return True
            
        except Exception as e:
            print(f"Failed to send SMS to {phone_number}: {str(e)}")
            return False
    
    @staticmethod
    def create_notification_record(household_id, member_name, chore_title, notification_type, message, chore_id=None):
        """Create a notification record in the database"""
        try:
            notification = Notification(
                household_id=household_id,
                member_name=member_name,
                chore_title=chore_title,
                notification_type=notification_type,
                message=message,
                chore_id=chore_id
            )
            db.session.add(notification)
            db.session.commit()
            return True
        except Exception as e:
            print(f"Failed to create notification record: {str(e)}")
            db.session.rollback()
            return False

# Rotation Service
class RotationService:
    @staticmethod
    def rotate_chores(household_id, rotation_type):
        """Rotate chores based on rotation type"""
        try:
            household = Household.query.get(household_id)
            if not household:
                return False
                
            chores = Chore.query.filter_by(household_id=household_id).all()
            members = Member.query.filter_by(household_id=household_id).all()
            
            if not chores or not members:
                return False
                
            member_names = [member.name for member in members]
            
            for chore in chores:
                if chore.assigned_to:
                    # Find current member index
                    try:
                        current_index = member_names.index(chore.assigned_to)
                        # Move to next member (circular)
                        next_index = (current_index + 1) % len(member_names)
                        new_assigned_to = member_names[next_index]
                        
                        # Record rotation history
                        rotation_history = RotationHistory(
                            household_id=household_id,
                            chore_id=chore.id,
                            previous_assigned_to=chore.assigned_to,
                            new_assigned_to=new_assigned_to,
                            rotation_type=rotation_type
                        )
                        db.session.add(rotation_history)
                        
                        # Update chore assignment
                        chore.assigned_to = new_assigned_to
                        chore.completed = False  # Reset completion status
                        
                    except ValueError:
                        # If assigned_to is not in current members, assign to first member
                        chore.assigned_to = member_names[0]
                        chore.completed = False
            
            db.session.commit()
            
            # Send rotation notifications
            for member in members:
                member_chores = [c for c in chores if c.assigned_to == member.name]
                if member_chores:
                    chore_list = ", ".join([c.title for c in member_chores])
                    message = f"Chore rotation complete! Your new chores: {chore_list}"
                    
                    # Send notification
                    NotificationService.create_notification_record(
                        household_id=household_id,
                        member_name=member.name,
                        chore_title="Rotation Complete",
                        notification_type="rotation",
                        message=message
                    )
                    
                    # Send email if preferences exist
                    preference = MemberPreference.query.filter_by(
                        household_id=household_id, 
                        member_name=member.name
                    ).first()
                    
                    if preference and preference.email and preference.notification_enabled:
                        NotificationService.send_email_notification(
                            preference.email,
                            f"HomeSync: New Chores Assigned",
                            message
                        )
            
            return True
            
        except Exception as e:
            print(f"Failed to rotate chores: {str(e)}")
            db.session.rollback()
            return False
    
    @staticmethod
    def should_rotate(household_id):
        """Check if chores should be rotated based on household settings"""
        try:
            household = Household.query.get(household_id)
            if not household or household.rotation_mode == 'none':
                return False
                
            # Get last rotation date
            last_rotation = RotationHistory.query.filter_by(
                household_id=household_id
            ).order_by(RotationHistory.rotation_date.desc()).first()
            
            if not last_rotation:
                return True  # First rotation
                
            now = datetime.now()
            days_since_rotation = (now - last_rotation.rotation_date).days
            
            if household.rotation_mode == 'weekly' and days_since_rotation >= 7:
                return True
            elif household.rotation_mode == 'biweekly' and days_since_rotation >= 14:
                return True
            elif household.rotation_mode == 'monthly' and days_since_rotation >= 30:
                return True
                
            return False
            
        except Exception as e:
            print(f"Failed to check rotation status: {str(e)}")
            return False

# Scheduled Tasks
def run_scheduled_tasks():
    """Run scheduled tasks for notifications and rotations"""
    while True:
        try:
            with app.app_context():
                # Check for overdue chores
                households = Household.query.all()
                for household in households:
                    try:
                        # Check if rotation is needed
                        if RotationService.should_rotate(household.id):
                            RotationService.rotate_chores(household.id, household.rotation_mode)
                        
                        # Check for overdue chores
                        chores = Chore.query.filter_by(household_id=household.id, completed=False).all()
                        for chore in chores:
                            if chore.days:
                                # Check if today is a chore day and it's overdue
                                today = datetime.now().strftime('%A')
                                if today in chore.days:
                                    # Check if it's past reminder time
                                    preference = MemberPreference.query.filter_by(
                                        household_id=household.id,
                                        member_name=chore.assigned_to
                                    ).first()
                                    
                                    if preference and preference.notification_enabled:
                                        reminder_time = preference.reminder_time
                                        current_time = datetime.now().strftime('%H:%M')
                                        
                                        if current_time >= reminder_time:
                                            message = f"Reminder: {chore.title} is due today!"
                                            
                                            # Send notification
                                            NotificationService.create_notification_record(
                                                household_id=household.id,
                                                member_name=chore.assigned_to,
                                                chore_title=chore.title,
                                                notification_type="reminder",
                                                message=message,
                                                chore_id=chore.id
                                            )
                                            
                                            # Send email if configured
                                            if preference.email:
                                                NotificationService.send_email_notification(
                                                    preference.email,
                                                    f"HomeSync Reminder: {chore.title}",
                                                    message
                                                )
                    except Exception as household_error:
                        print(f"Error processing household {household.id}: {str(household_error)}")
                        continue
            
            time.sleep(3600)  # Check every hour
            
        except Exception as e:
            print(f"Scheduled task error: {str(e)}")
            time.sleep(3600)

# Routes
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'Chore Management API is running'})

@app.route('/households', methods=['POST'])
def create_household():
    """Create a new household"""
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Household name is required'}), 400
    
    try:
        # Generate unique code
        code = generate_household_code()
        
        # Create household
        household = Household(name=data['name'], code=code)
        db.session.add(household)
        db.session.commit()
        
        return jsonify({
            'message': 'Household created successfully',
            'household': household.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create household'}), 500

@app.route('/households/<code>', methods=['GET'])
def get_household(code):
    """Get household details by code"""
    household = Household.query.filter_by(code=code).first()
    if not household:
        return jsonify({'error': 'Household not found'}), 404
    
    return jsonify({
        'household': household.to_dict(),
        'members': [member.to_dict() for member in household.members],
        'chores': [chore.to_dict() for chore in household.chores]
    })

@app.route('/households/<code>/join', methods=['POST'])
def join_household(code):
    """Join an existing household with enhanced validation"""
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Member name is required'}), 400
    
    # Find household by code
    household = Household.query.filter_by(code=code).first()
    if not household:
        return jsonify({'error': 'Household not found'}), 404
    
    # Check if member already exists
    existing_member = Member.query.filter_by(
        household_id=household.id, 
        name=data['name']
    ).first()
    
    if existing_member:
        return jsonify({
            'message': 'Member already exists in household',
            'member': existing_member.to_dict(),
            'household': household.to_dict()
        }), 200
    
    try:
        # Create member
        member = Member(
            name=data['name'],
            is_admin=data.get('is_admin', False),
            household_id=household.id
        )
        db.session.add(member)
        
        # Create default member preferences
        preference = MemberPreference(
            member_name=data['name'],
            household_id=household.id,
            email=data.get('email'),
            phone=data.get('phone'),
            notification_enabled=data.get('notification_enabled', True),
            reminder_time=data.get('reminder_time', '09:00'),
            reminder_days_before=data.get('reminder_days_before', 1)
        )
        db.session.add(preference)
        
        db.session.commit()
        
        # Send welcome notification
        welcome_message = f"Welcome to {household.name}! You've successfully joined the household."
        NotificationService.create_notification_record(
            household_id=household.id,
            member_name=data['name'],
            chore_title="Welcome",
            notification_type="welcome",
            message=welcome_message
        )
        
        return jsonify({
            'message': 'Successfully joined household',
            'member': member.to_dict(),
            'household': household.to_dict(),
            'preferences': preference.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to join household'}), 500

@app.route('/households/<code>/chores', methods=['GET'])
def get_household_chores(code):
    """Get all chores for a household"""
    household = Household.query.filter_by(code=code).first()
    if not household:
        return jsonify({'error': 'Household not found'}), 404
    
    chores = Chore.query.filter_by(household_id=household.id).all()
    return jsonify([chore.to_dict() for chore in chores])

@app.route('/households/<code>/chores', methods=['POST'])
def create_chore(code):
    """Create a new chore for a household"""
    household = Household.query.filter_by(code=code).first()
    if not household:
        return jsonify({'error': 'Household not found'}), 404
    
    data = request.get_json()
    if not data or 'title' not in data or 'days' not in data:
        return jsonify({'error': 'Title and days are required'}), 400
    
    try:
        chore = Chore(
            title=data['title'],
            description=data.get('description', ''),
            days=data['days'],
            assigned_to=data.get('assigned_to'),
            household_id=household.id
        )
        db.session.add(chore)
        db.session.commit()
        
        return jsonify({
            'message': 'Chore created successfully',
            'chore': chore.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create chore'}), 500

@app.route('/chores/<int:chore_id>', methods=['PUT'])
def update_chore(chore_id):
    """Update a chore"""
    chore = Chore.query.get_or_404(chore_id)
    data = request.get_json()
    
    try:
        if 'title' in data:
            chore.title = data['title']
        if 'description' in data:
            chore.description = data['description']
        if 'days' in data:
            chore.days = data['days']
        if 'assigned_to' in data:
            chore.assigned_to = data['assigned_to']
        if 'completed' in data:
            chore.completed = data['completed']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Chore updated successfully',
            'chore': chore.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update chore'}), 500

@app.route('/chores/<int:chore_id>', methods=['DELETE'])
def delete_chore(chore_id):
    """Delete a chore"""
    chore = Chore.query.get_or_404(chore_id)
    
    try:
        db.session.delete(chore)
        db.session.commit()
        
        return jsonify({'message': 'Chore deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete chore'}), 500

@app.route('/households/<code>/members', methods=['GET'])
def get_household_members(code):
    """Get all members of a household"""
    household = Household.query.filter_by(code=code).first()
    if not household:
        return jsonify({'error': 'Household not found'}), 404
    
    members = Member.query.filter_by(household_id=household.id).all()
    return jsonify([member.to_dict() for member in members])

@app.route('/households/<code>', methods=['DELETE'])
def delete_household(code):
    """Delete a household and all its data"""
    household = Household.query.filter_by(code=code).first()
    if not household:
        return jsonify({'error': 'Household not found'}), 404
    
    try:
        # Delete all related data
        Chore.query.filter_by(household_id=household.id).delete()
        Member.query.filter_by(household_id=household.id).delete()
        Notification.query.filter_by(household_id=household.id).delete()
        RotationHistory.query.filter_by(household_id=household.id).delete()
        MemberPreference.query.filter_by(household_id=household.id).delete()
        db.session.delete(household)
        db.session.commit()
        
        return jsonify({'message': 'Household deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete household'}), 500

# Notification endpoints
@app.route('/households/<code>/notifications', methods=['GET'])
def get_household_notifications(code):
    """Get all notifications for a household"""
    household = Household.query.filter_by(code=code).first()
    if not household:
        return jsonify({'error': 'Household not found'}), 404
    
    notifications = Notification.query.filter_by(household_id=household.id).order_by(Notification.sent_at.desc()).all()
    return jsonify([notification.to_dict() for notification in notifications])

@app.route('/households/<code>/notifications', methods=['POST'])
def send_notification(code):
    """Send a custom notification to household members"""
    household = Household.query.filter_by(code=code).first()
    if not household:
        return jsonify({'error': 'Household not found'}), 404
    
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'Message is required'}), 400
    
    try:
        members = Member.query.filter_by(household_id=household.id).all()
        sent_count = 0
        
        for member in members:
            # Create notification record
            NotificationService.create_notification_record(
                household_id=household.id,
                member_name=member.name,
                chore_title="Custom Message",
                notification_type="custom",
                message=data['message']
            )
            
            # Send email if preferences exist
            preference = MemberPreference.query.filter_by(
                household_id=household.id,
                member_name=member.name
            ).first()
            
            if preference and preference.email and preference.notification_enabled:
                NotificationService.send_email_notification(
                    preference.email,
                    f"HomeSync Message from {household.name}",
                    data['message']
                )
                sent_count += 1
        
        return jsonify({
            'message': f'Notification sent to {sent_count} members',
            'total_members': len(members)
        })
        
    except Exception as e:
        return jsonify({'error': 'Failed to send notification'}), 500

# Member preferences endpoints
@app.route('/households/<code>/members/<member_name>/preferences', methods=['GET'])
def get_member_preferences(code, member_name):
    """Get member preferences"""
    household = Household.query.filter_by(code=code).first()
    if not household:
        return jsonify({'error': 'Household not found'}), 404
    
    preference = MemberPreference.query.filter_by(
        household_id=household.id,
        member_name=member_name
    ).first()
    
    if not preference:
        return jsonify({'error': 'Member preferences not found'}), 404
    
    return jsonify(preference.to_dict())

@app.route('/households/<code>/members/<member_name>/preferences', methods=['PUT'])
def update_member_preferences(code, member_name):
    """Update member preferences"""
    household = Household.query.filter_by(code=code).first()
    if not household:
        return jsonify({'error': 'Household not found'}), 404
    
    preference = MemberPreference.query.filter_by(
        household_id=household.id,
        member_name=member_name
    ).first()
    
    if not preference:
        return jsonify({'error': 'Member preferences not found'}), 404
    
    data = request.get_json()
    
    try:
        if 'email' in data:
            preference.email = data['email']
        if 'phone' in data:
            preference.phone = data['phone']
        if 'notification_enabled' in data:
            preference.notification_enabled = data['notification_enabled']
        if 'reminder_time' in data:
            preference.reminder_time = data['reminder_time']
        if 'reminder_days_before' in data:
            preference.reminder_days_before = data['reminder_days_before']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Preferences updated successfully',
            'preferences': preference.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update preferences'}), 500

# Rotation endpoints
@app.route('/households/<code>/rotate', methods=['POST'])
def manual_rotate_chores(code):
    """Manually trigger chore rotation"""
    household = Household.query.filter_by(code=code).first()
    if not household:
        return jsonify({'error': 'Household not found'}), 404
    
    try:
        success = RotationService.rotate_chores(household.id, household.rotation_mode)
        
        if success:
            return jsonify({'message': 'Chores rotated successfully'})
        else:
            return jsonify({'error': 'Failed to rotate chores'}), 500
            
    except Exception as e:
        return jsonify({'error': 'Failed to rotate chores'}), 500

@app.route('/households/<code>/rotation-history', methods=['GET'])
def get_rotation_history(code):
    """Get rotation history for a household"""
    household = Household.query.filter_by(code=code).first()
    if not household:
        return jsonify({'error': 'Household not found'}), 404
    
    history = RotationHistory.query.filter_by(household_id=household.id).order_by(RotationHistory.rotation_date.desc()).all()
    return jsonify([record.to_dict() for record in history])

# Utility endpoints
@app.route('/households/<code>/status', methods=['GET'])
def get_household_status(code):
    """Get comprehensive household status"""
    household = Household.query.filter_by(code=code).first()
    if not household:
        return jsonify({'error': 'Household not found'}), 404
    
    # Get statistics
    total_chores = Chore.query.filter_by(household_id=household.id).count()
    completed_chores = Chore.query.filter_by(household_id=household.id, completed=True).count()
    total_members = Member.query.filter_by(household_id=household.id).count()
    
    # Check if rotation is needed
    needs_rotation = RotationService.should_rotate(household.id)
    
    # Get recent notifications
    recent_notifications = Notification.query.filter_by(household_id=household.id).order_by(Notification.sent_at.desc()).limit(5).all()
    
    return jsonify({
        'household': household.to_dict(),
        'stats': {
            'total_chores': total_chores,
            'completed_chores': completed_chores,
            'completion_rate': round((completed_chores / total_chores * 100) if total_chores > 0 else 0, 1),
            'total_members': total_members,
            'needs_rotation': needs_rotation
        },
        'recent_notifications': [n.to_dict() for n in recent_notifications]
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    port = int(os.getenv('PORT', 5001))
    host = os.getenv('HOST', '0.0.0.0')
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"Starting HomeSync API server on {host}:{port}")
    
    # Start scheduled tasks in a separate thread only if not in debug mode
    # In debug mode, Flask restarts frequently which causes issues with background threads
    if not debug:
        scheduler_thread = threading.Thread(target=run_scheduled_tasks, daemon=True)
        scheduler_thread.start()
        print("Scheduled tasks started for notifications and rotations")
    else:
        print("Scheduled tasks disabled in debug mode")
    
    app.run(host=host, port=port, debug=debug)
