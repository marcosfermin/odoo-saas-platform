#!/usr/bin/env python3
"""
Support Tickets API
Handles customer support ticket management
"""

import os
import sys
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from shared.models import SupportTicket, Customer
from portal.app import db, limiter
from portal.app.utils.validation import validate_json
from portal.app.utils.auth import require_customer

# Create blueprint
support_bp = Blueprint('support', __name__)

# Input validation schemas
TICKET_CREATE_SCHEMA = {
    'type': 'object',
    'properties': {
        'subject': {
            'type': 'string',
            'minLength': 3,
            'maxLength': 200
        },
        'description': {
            'type': 'string',
            'minLength': 10,
            'maxLength': 5000
        },
        'priority': {
            'type': 'string',
            'enum': ['low', 'medium', 'high', 'urgent']
        },
        'category': {
            'type': 'string',
            'enum': ['billing', 'technical', 'feature_request', 'other']
        }
    },
    'required': ['subject', 'description', 'category'],
    'additionalProperties': False
}

TICKET_UPDATE_SCHEMA = {
    'type': 'object',
    'properties': {
        'description': {
            'type': 'string',
            'minLength': 10,
            'maxLength': 5000
        }
    },
    'required': ['description'],
    'additionalProperties': False
}

@support_bp.route('/', methods=['GET'])
@jwt_required()
@require_customer
@limiter.limit("30 per minute")
def list_tickets():
    """List support tickets for current customer"""
    try:
        customer_id = get_jwt_identity()
        
        # Query parameters
        status = request.args.get('status')
        category = request.args.get('category')
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        
        # Build query
        query = db.session.query(SupportTicket).filter_by(customer_id=customer_id)
        
        if status:
            query = query.filter(SupportTicket.status == status)
        if category:
            query = query.filter(SupportTicket.category == category)
        
        # Order by creation date (newest first)
        query = query.order_by(SupportTicket.created_at.desc())
        
        # Paginate
        tickets = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return jsonify({
            'tickets': [{
                'id': ticket.id,
                'subject': ticket.subject,
                'status': ticket.status,
                'priority': ticket.priority,
                'category': ticket.category,
                'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
                'updated_at': ticket.updated_at.isoformat() if ticket.updated_at else None,
                'last_response_at': ticket.last_response_at.isoformat() if ticket.last_response_at else None
            } for ticket in tickets.items],
            'pagination': {
                'page': tickets.page,
                'pages': tickets.pages,
                'per_page': tickets.per_page,
                'total': tickets.total,
                'has_next': tickets.has_next,
                'has_prev': tickets.has_prev
            }
        }), 200
        
    except ValueError:
        return jsonify({'error': 'Invalid pagination parameters'}), 400
    except Exception as e:
        current_app.logger.error(f"Error listing tickets: {e}")
        return jsonify({'error': 'Failed to list tickets'}), 500

@support_bp.route('/', methods=['POST'])
@jwt_required()
@require_customer
@limiter.limit("5 per minute")
def create_ticket():
    """Create a new support ticket"""
    try:
        customer_id = get_jwt_identity()
        
        # Validate input
        data = validate_json(request, TICKET_CREATE_SCHEMA)
        
        # Check customer exists
        customer = db.session.get(Customer, customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        # Create ticket
        ticket = SupportTicket(
            customer_id=customer_id,
            subject=data['subject'],
            description=data['description'],
            priority=data.get('priority', 'medium'),
            category=data['category'],
            status='open'
        )
        
        db.session.add(ticket)
        db.session.commit()
        
        # TODO: Send notification to support team
        current_app.logger.info(f"Support ticket created: {ticket.id} for customer {customer_id}")
        
        return jsonify({
            'id': ticket.id,
            'subject': ticket.subject,
            'description': ticket.description,
            'status': ticket.status,
            'priority': ticket.priority,
            'category': ticket.category,
            'created_at': ticket.created_at.isoformat(),
            'updated_at': ticket.updated_at.isoformat()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating ticket: {e}")
        return jsonify({'error': 'Failed to create ticket'}), 500

@support_bp.route('/<int:ticket_id>', methods=['GET'])
@jwt_required()
@require_customer
@limiter.limit("60 per minute")
def get_ticket(ticket_id):
    """Get a specific support ticket"""
    try:
        customer_id = get_jwt_identity()
        
        # Find ticket
        ticket = db.session.query(SupportTicket).filter_by(
            id=ticket_id,
            customer_id=customer_id
        ).first()
        
        if not ticket:
            return jsonify({'error': 'Ticket not found'}), 404
        
        return jsonify({
            'id': ticket.id,
            'subject': ticket.subject,
            'description': ticket.description,
            'status': ticket.status,
            'priority': ticket.priority,
            'category': ticket.category,
            'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
            'updated_at': ticket.updated_at.isoformat() if ticket.updated_at else None,
            'last_response_at': ticket.last_response_at.isoformat() if ticket.last_response_at else None,
            'resolution': ticket.resolution,
            'resolved_at': ticket.resolved_at.isoformat() if ticket.resolved_at else None
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting ticket: {e}")
        return jsonify({'error': 'Failed to get ticket'}), 500

@support_bp.route('/<int:ticket_id>', methods=['PUT'])
@jwt_required()
@require_customer
@limiter.limit("10 per minute")
def update_ticket(ticket_id):
    """Update a support ticket (add customer response)"""
    try:
        customer_id = get_jwt_identity()
        
        # Validate input
        data = validate_json(request, TICKET_UPDATE_SCHEMA)
        
        # Find ticket
        ticket = db.session.query(SupportTicket).filter_by(
            id=ticket_id,
            customer_id=customer_id
        ).first()
        
        if not ticket:
            return jsonify({'error': 'Ticket not found'}), 404
        
        # Check if ticket is closed
        if ticket.status == 'closed':
            return jsonify({'error': 'Cannot update closed ticket'}), 400
        
        # Add customer response (append to description)
        separator = "\n\n--- Customer Response ---\n"
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        response = f"{separator}[{timestamp}] {data['description']}"
        
        ticket.description += response
        ticket.updated_at = datetime.utcnow()
        
        # Reopen ticket if it was resolved
        if ticket.status == 'resolved':
            ticket.status = 'open'
            ticket.resolved_at = None
        
        db.session.commit()
        
        current_app.logger.info(f"Support ticket updated: {ticket.id}")
        
        return jsonify({
            'id': ticket.id,
            'subject': ticket.subject,
            'description': ticket.description,
            'status': ticket.status,
            'priority': ticket.priority,
            'category': ticket.category,
            'updated_at': ticket.updated_at.isoformat()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating ticket: {e}")
        return jsonify({'error': 'Failed to update ticket'}), 500

@support_bp.route('/<int:ticket_id>/close', methods=['POST'])
@jwt_required()
@require_customer
@limiter.limit("10 per minute")
def close_ticket(ticket_id):
    """Close a support ticket"""
    try:
        customer_id = get_jwt_identity()
        
        # Find ticket
        ticket = db.session.query(SupportTicket).filter_by(
            id=ticket_id,
            customer_id=customer_id
        ).first()
        
        if not ticket:
            return jsonify({'error': 'Ticket not found'}), 404
        
        # Check if already closed
        if ticket.status == 'closed':
            return jsonify({'error': 'Ticket already closed'}), 400
        
        # Close ticket
        ticket.status = 'closed'
        ticket.resolved_at = datetime.utcnow()
        ticket.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        current_app.logger.info(f"Support ticket closed: {ticket.id}")
        
        return jsonify({
            'id': ticket.id,
            'status': ticket.status,
            'resolved_at': ticket.resolved_at.isoformat(),
            'message': 'Ticket closed successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error closing ticket: {e}")
        return jsonify({'error': 'Failed to close ticket'}), 500

@support_bp.route('/stats', methods=['GET'])
@jwt_required()
@require_customer
@limiter.limit("10 per minute")
def get_stats():
    """Get support ticket statistics for current customer"""
    try:
        customer_id = get_jwt_identity()
        
        # Get ticket counts by status
        open_count = db.session.query(SupportTicket).filter_by(
            customer_id=customer_id,
            status='open'
        ).count()
        
        in_progress_count = db.session.query(SupportTicket).filter_by(
            customer_id=customer_id,
            status='in_progress'
        ).count()
        
        resolved_count = db.session.query(SupportTicket).filter_by(
            customer_id=customer_id,
            status='resolved'
        ).count()
        
        closed_count = db.session.query(SupportTicket).filter_by(
            customer_id=customer_id,
            status='closed'
        ).count()
        
        total_count = open_count + in_progress_count + resolved_count + closed_count
        
        # Get recent tickets (last 30 days)
        from datetime import timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        recent_count = db.session.query(SupportTicket).filter(
            SupportTicket.customer_id == customer_id,
            SupportTicket.created_at >= thirty_days_ago
        ).count()
        
        return jsonify({
            'total': total_count,
            'open': open_count,
            'in_progress': in_progress_count,
            'resolved': resolved_count,
            'closed': closed_count,
            'recent_30_days': recent_count
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting ticket stats: {e}")
        return jsonify({'error': 'Failed to get statistics'}), 500

# Health check
@support_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'support',
        'timestamp': datetime.utcnow().isoformat()
    }), 200