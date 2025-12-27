#!/usr/bin/env python3
"""
Notification Background Jobs
Handles email notifications and alerts
"""

import os
import sys
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)

# Email configuration
SMTP_HOST = os.environ.get('SMTP_HOST', 'localhost')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
SMTP_FROM = os.environ.get('SMTP_FROM', 'noreply@example.com')
SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true'

PORTAL_URL = os.environ.get('PORTAL_URL', 'http://localhost:5001')
COMPANY_NAME = os.environ.get('COMPANY_NAME', 'Odoo SaaS Platform')


def send_email(to_email, subject, html_content, text_content=None):
    """
    Send email via SMTP

    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        html_content (str): HTML email body
        text_content (str, optional): Plain text fallback

    Returns:
        bool: True if email sent successfully
    """
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = SMTP_FROM
        msg['To'] = to_email

        # Add plain text version
        if text_content:
            part1 = MIMEText(text_content, 'plain')
            msg.attach(part1)

        # Add HTML version
        part2 = MIMEText(html_content, 'html')
        msg.attach(part2)

        # Send email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_USE_TLS:
                server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())

        logger.info(f"Email sent successfully to {to_email}: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        raise


def send_verification_email(customer_id, email, verification_link):
    """
    Send email verification email

    Args:
        customer_id (str): Customer ID
        email (str): Customer email
        verification_link (str): Verification URL
    """
    logger.info(f"Sending verification email to {email}")

    subject = f"Verify your email - {COMPANY_NAME}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                background-color: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .footer {{ margin-top: 40px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Verify your email address</h1>
            <p>Thank you for signing up with {COMPANY_NAME}!</p>
            <p>Please click the button below to verify your email address:</p>
            <a href="{verification_link}" class="button">Verify Email</a>
            <p>Or copy and paste this link into your browser:</p>
            <p><a href="{verification_link}">{verification_link}</a></p>
            <p>If you didn't create an account with us, please ignore this email.</p>
            <div class="footer">
                <p>&copy; {datetime.now().year} {COMPANY_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"""
    Verify your email address

    Thank you for signing up with {COMPANY_NAME}!

    Please click the link below to verify your email address:
    {verification_link}

    If you didn't create an account with us, please ignore this email.

    {COMPANY_NAME}
    """

    send_email(email, subject, html_content, text_content)

    logger.info(f"Verification email sent to {email}")
    return {'status': 'sent', 'email': email}


def send_password_reset_email(customer_id, email, reset_link):
    """
    Send password reset email

    Args:
        customer_id (str): Customer ID
        email (str): Customer email
        reset_link (str): Password reset URL
    """
    logger.info(f"Sending password reset email to {email}")

    subject = f"Reset your password - {COMPANY_NAME}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                background-color: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .warning {{ color: #dc3545; font-weight: bold; }}
            .footer {{ margin-top: 40px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Reset your password</h1>
            <p>We received a request to reset your password for your {COMPANY_NAME} account.</p>
            <p>Click the button below to reset your password:</p>
            <a href="{reset_link}" class="button">Reset Password</a>
            <p>Or copy and paste this link into your browser:</p>
            <p><a href="{reset_link}">{reset_link}</a></p>
            <p class="warning">This link will expire in 1 hour.</p>
            <p>If you didn't request a password reset, please ignore this email. Your password will remain unchanged.</p>
            <div class="footer">
                <p>&copy; {datetime.now().year} {COMPANY_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"""
    Reset your password

    We received a request to reset your password for your {COMPANY_NAME} account.

    Click the link below to reset your password:
    {reset_link}

    This link will expire in 1 hour.

    If you didn't request a password reset, please ignore this email.

    {COMPANY_NAME}
    """

    send_email(email, subject, html_content, text_content)

    logger.info(f"Password reset email sent to {email}")
    return {'status': 'sent', 'email': email}


def send_trial_ending_email(customer_id, subscription_id, trial_end_date):
    """
    Send trial ending notification email

    Args:
        customer_id (str): Customer ID
        subscription_id (str): Subscription ID
        trial_end_date (str): Trial end date ISO string
    """
    from shared.models import Customer, Subscription
    from shared.database import get_db_session

    with get_db_session() as session:
        customer = session.query(Customer).get(customer_id)
        subscription = session.query(Subscription).get(subscription_id)

        if not customer or not subscription:
            logger.warning(f"Customer or subscription not found: {customer_id}, {subscription_id}")
            return {'status': 'skipped', 'reason': 'not_found'}

        email = customer.email
        plan_name = subscription.plan.name if subscription.plan else 'your plan'

    logger.info(f"Sending trial ending email to {email}")

    subject = f"Your trial is ending soon - {COMPANY_NAME}"

    billing_url = f"{PORTAL_URL}/billing"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                background-color: #28a745;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .highlight {{ background-color: #fff3cd; padding: 15px; border-radius: 4px; margin: 20px 0; }}
            .footer {{ margin-top: 40px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Your trial is ending soon</h1>
            <div class="highlight">
                <p>Your free trial of <strong>{plan_name}</strong> will end on <strong>{trial_end_date}</strong>.</p>
            </div>
            <p>To continue using {COMPANY_NAME} and keep access to all your data, please add a payment method before your trial ends.</p>
            <a href="{billing_url}" class="button">Manage Billing</a>
            <p>If you have any questions or need help choosing the right plan, our support team is here to help!</p>
            <div class="footer">
                <p>&copy; {datetime.now().year} {COMPANY_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"""
    Your trial is ending soon

    Your free trial of {plan_name} will end on {trial_end_date}.

    To continue using {COMPANY_NAME} and keep access to all your data, please add a payment method before your trial ends.

    Manage your billing: {billing_url}

    If you have any questions, our support team is here to help!

    {COMPANY_NAME}
    """

    send_email(email, subject, html_content, text_content)

    logger.info(f"Trial ending email sent to {email}")
    return {'status': 'sent', 'email': email}


def send_welcome_email(customer_id, email, first_name):
    """
    Send welcome email to new customer

    Args:
        customer_id (str): Customer ID
        email (str): Customer email
        first_name (str): Customer first name
    """
    logger.info(f"Sending welcome email to {email}")

    subject = f"Welcome to {COMPANY_NAME}!"

    dashboard_url = f"{PORTAL_URL}/dashboard"
    docs_url = f"{PORTAL_URL}/docs"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                background-color: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .features {{ background-color: #f8f9fa; padding: 20px; border-radius: 4px; margin: 20px 0; }}
            .footer {{ margin-top: 40px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Welcome to {COMPANY_NAME}, {first_name}!</h1>
            <p>Thank you for signing up! We're excited to have you on board.</p>
            <div class="features">
                <h3>Here's what you can do:</h3>
                <ul>
                    <li>Create and manage Odoo instances</li>
                    <li>Install modules and customize your setup</li>
                    <li>Monitor usage and manage billing</li>
                    <li>Access 24/7 support</li>
                </ul>
            </div>
            <a href="{dashboard_url}" class="button">Go to Dashboard</a>
            <p>Need help getting started? Check out our <a href="{docs_url}">documentation</a>.</p>
            <div class="footer">
                <p>&copy; {datetime.now().year} {COMPANY_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"""
    Welcome to {COMPANY_NAME}, {first_name}!

    Thank you for signing up! We're excited to have you on board.

    Here's what you can do:
    - Create and manage Odoo instances
    - Install modules and customize your setup
    - Monitor usage and manage billing
    - Access 24/7 support

    Go to your dashboard: {dashboard_url}

    Need help getting started? Check out our documentation: {docs_url}

    {COMPANY_NAME}
    """

    send_email(email, subject, html_content, text_content)

    logger.info(f"Welcome email sent to {email}")
    return {'status': 'sent', 'email': email}


def send_tenant_ready_email(customer_id, tenant_slug, tenant_name, tenant_url):
    """
    Send notification when tenant is ready

    Args:
        customer_id (str): Customer ID
        tenant_slug (str): Tenant slug
        tenant_name (str): Tenant name
        tenant_url (str): Tenant URL
    """
    from shared.models import Customer
    from shared.database import get_db_session

    with get_db_session() as session:
        customer = session.query(Customer).get(customer_id)
        if not customer:
            logger.warning(f"Customer not found: {customer_id}")
            return {'status': 'skipped', 'reason': 'not_found'}
        email = customer.email
        first_name = customer.first_name or 'there'

    logger.info(f"Sending tenant ready email to {email}")

    subject = f"Your Odoo instance is ready! - {COMPANY_NAME}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                background-color: #28a745;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .info-box {{ background-color: #e7f3ff; padding: 20px; border-radius: 4px; margin: 20px 0; }}
            .footer {{ margin-top: 40px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Your Odoo instance is ready!</h1>
            <p>Hi {first_name},</p>
            <p>Great news! Your Odoo instance <strong>{tenant_name}</strong> has been provisioned and is ready to use.</p>
            <div class="info-box">
                <p><strong>Instance Name:</strong> {tenant_name}</p>
                <p><strong>URL:</strong> <a href="{tenant_url}">{tenant_url}</a></p>
            </div>
            <a href="{tenant_url}" class="button">Access Your Instance</a>
            <p>You can start customizing your Odoo instance by installing modules from your dashboard.</p>
            <div class="footer">
                <p>&copy; {datetime.now().year} {COMPANY_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"""
    Your Odoo instance is ready!

    Hi {first_name},

    Great news! Your Odoo instance {tenant_name} has been provisioned and is ready to use.

    Instance Name: {tenant_name}
    URL: {tenant_url}

    You can start customizing your Odoo instance by installing modules from your dashboard.

    {COMPANY_NAME}
    """

    send_email(email, subject, html_content, text_content)

    logger.info(f"Tenant ready email sent to {email}")
    return {'status': 'sent', 'email': email}
