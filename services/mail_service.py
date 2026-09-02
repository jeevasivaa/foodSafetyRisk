"""
services/mail_service.py — Email Notification Service
"""
from flask_mail import Mail, Message
from flask import render_template_string, current_app
from threading import Thread
import config

# Global mail instance
mail = Mail()

def send_async_email(app, msg):
    """Sends email asynchronously to prevent blocking the web request."""
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            print(f"Failed to send email: {e}")

def send_email(subject, recipient, body, html=None):
    """Generic function to send an email."""
    if not recipient:
        return
        
    msg = Message(subject, recipients=[recipient])
    msg.body = body
    if html:
        msg.html = html
        
    # Run in background
    Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()


# ─── Email Templates ──────────────────────────────────────────────────────────

def send_welcome_email(user_email, user_name):
    """Send welcome email upon successful registration."""
    subject = "Welcome to Food Quality Analysis System!"
    
    html = f"""
    <h2>Welcome to the Food Quality Analysis System, {user_name}!</h2>
    <p>We are thrilled to have you on board. You can now start scanning food products and raising complaints to ensure food safety.</p>
    <br>
    <p>Stay safe,<br>The Food Quality AI Team</p>
    """
    
    send_email(subject, user_email, "Welcome to Food Quality Analysis!", html=html)


def send_complaint_acknowledgement(user_email, user_name, complaint_title):
    """Send acknowledgment to the customer when they raise a complaint."""
    subject = f"Complaint Received: {complaint_title}"
    
    html = f"""
    <h3>Hi {user_name},</h3>
    <p>We have successfully received your complaint: <strong>{complaint_title}</strong>.</p>
    <p>Our administration team will review it shortly. You can track the status in your dashboard.</p>
    <br>
    <p>Thank you,<br>The Food Quality AI Team</p>
    """
    
    send_email(subject, user_email, f"Complaint received: {complaint_title}", html=html)


def send_admin_notification(complaint_title, submitted_by):
    """Notify the admin when a new complaint is filed."""
    subject = f"ACTION REQUIRED: New Complaint Filed - {complaint_title}"
    
    html = f"""
    <h3>New Complaint Submitted</h3>
    <p>A new complaint titled <strong>{complaint_title}</strong> has been filed by {submitted_by}.</p>
    <p>Please log in to the admin dashboard to review and resolve the issue.</p>
    """
    
    # Send to admin email from config
    send_email(subject, config.ADMIN_EMAIL, "New complaint requires attention.", html=html)


def send_complaint_status_update(user_email, user_name, complaint_title, new_status, response_text):
    """Notify the customer when an admin updates their complaint status."""
    subject = f"Update on your complaint: {complaint_title}"
    
    html = f"""
    <h3>Hi {user_name},</h3>
    <p>There has been an update regarding your complaint: <strong>{complaint_title}</strong>.</p>
    <p><strong>New Status:</strong> {new_status}</p>
    """
    
    if response_text:
        html += f"""
        <p><strong>Admin Response:</strong></p>
        <blockquote style="border-left: 4px solid #ccc; padding-left: 10px; margin-left: 0;">
            {response_text}
        </blockquote>
        """
        
    html += "<br><p>Thank you,<br>The Food Quality AI Team</p>"
    
    send_email(subject, user_email, f"Your complaint is now {new_status}.", html=html)
