"""Ticketing Support App - Flask backend for managing support tickets."""

import logging
import os
from datetime import datetime

from databricks.sdk import WorkspaceClient
from flask import Flask, jsonify, render_template, request

import lakebase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ticketing-app")

app = Flask(__name__)
_w = WorkspaceClient()

# Table names - using existing tables from ticketing system database
TICKETS_TABLE = "tickets"
MESSAGES_TABLE = "ticket_messages"


def _current_user_email() -> str:
    """Get the current logged-in user's email."""
    header_email = request.headers.get("X-Forwarded-Email")
    if header_email:
        return header_email
    return _w.current_user.me().user_name


def ensure_tables():
    """Tables already exist in the ticketing system database - just verify connectivity."""
    # Verify tables exist by checking their structure
    try:
        lakebase.run_query(f"SELECT 1 FROM {TICKETS_TABLE} LIMIT 1")
        lakebase.run_query(f"SELECT 1 FROM {MESSAGES_TABLE} LIMIT 1")
        logger.info("✅ Successfully connected to existing ticketing system tables")
    except Exception as e:
        logger.error(f"❌ Could not connect to ticketing system tables: {e}")
        raise


def generate_ticket_id() -> int:
    """Generate the next ticket ID as an integer."""
    result = lakebase.run_query(
        f"SELECT MAX(ticket_id) as max_id FROM {TICKETS_TABLE}"
    )
    if result and result[0].get('max_id') is not None:
        return result[0]['max_id'] + 1
    return 1  # Start from 1 if no tickets exist


def generate_message_id() -> int:
    """Generate the next message ID as an integer."""
    result = lakebase.run_query(
        f"SELECT MAX(message_id) as max_id FROM {MESSAGES_TABLE}"
    )
    if result and result[0].get('max_id') is not None:
        return result[0]['max_id'] + 1
    return 1  # Start from 1 if no messages exist


@app.route("/healthz")
def healthz():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


@app.errorhandler(Exception)
def handle_exception(err):
    """Global error handler."""
    logger.exception("Unhandled exception")
    status_code = getattr(err, "code", 500)
    if not isinstance(status_code, int):
        status_code = 500
    return jsonify({"error": str(err)}), status_code


@app.route("/")
def index():
    """Serve the main ticketing interface."""
    ensure_tables()
    user_email = _current_user_email()
    return render_template("tickets.html", user_email=user_email)


@app.route("/api/tickets", methods=["GET"])
def get_tickets():
    """Get all tickets, optionally filtered by status."""
    status_filter = request.args.get("status")
    user_email = _current_user_email()
    
    if status_filter and status_filter != "all":
        tickets = lakebase.run_query(f"""
            SELECT ticket_id, title, status, created_by, created_at 
            FROM {TICKETS_TABLE}
            WHERE status = %s
            ORDER BY created_at DESC
        """, (status_filter,))
    else:
        tickets = lakebase.run_query(f"""
            SELECT ticket_id, title, status, created_by, created_at 
            FROM {TICKETS_TABLE}
            ORDER BY created_at DESC
        """)
    
    return jsonify(tickets)


@app.route("/api/tickets", methods=["POST"])
def create_ticket():
    """Create a new support ticket."""
    data = request.json
    created_by = data.get("created_by", "").strip()
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    
    if not created_by:
        return jsonify({"error": "Name is required"}), 400
    if not title:
        return jsonify({"error": "Title is required"}), 400
    
    ticket_id = generate_ticket_id()
    
    # Insert using existing table schema: ticket_id, title, status, created_by, created_at
    # Status is always 'open' for new tickets
    lakebase.run_write(f"""
        INSERT INTO {TICKETS_TABLE} 
        (ticket_id, title, status, created_by, created_at)
        VALUES (%s, %s, %s, %s, now())
    """, (ticket_id, title, 'open', created_by))
    
    # Add initial message using existing schema: message_id, ticket_id, message_text, author, created_at
    if description:
        message_id = generate_message_id()
        lakebase.run_write(f"""
            INSERT INTO {MESSAGES_TABLE}
            (message_id, ticket_id, message_text, author, created_at)
            VALUES (%s, %s, %s, %s, now())
        """, (message_id, ticket_id, description, created_by))
    
    return jsonify({
        "ticket_id": ticket_id,
        "title": title,
        "status": "open"
    })


@app.route("/api/tickets/<ticket_id>", methods=["GET"])
def get_ticket(ticket_id):
    """Get a specific ticket with its details."""
    tickets = lakebase.run_query(f"""
        SELECT ticket_id, title, status, created_by, created_at 
        FROM {TICKETS_TABLE}
        WHERE ticket_id = %s
    """, (ticket_id,))
    
    if not tickets:
        return jsonify({"error": "Ticket not found"}), 404
    
    return jsonify(tickets[0])


@app.route("/api/tickets/<ticket_id>", methods=["PATCH"])
def update_ticket(ticket_id):
    """Update ticket status or other fields."""
    data = request.json
    status = data.get("status")
    
    if status:
        lakebase.run_write(f"""
            UPDATE {TICKETS_TABLE}
            SET status = %s
            WHERE ticket_id = %s
        """, (status, ticket_id))
    
    return jsonify({"ticket_id": ticket_id, "status": status})


@app.route("/api/tickets/<ticket_id>/messages", methods=["GET"])
def get_messages(ticket_id):
    """Get all messages for a ticket."""
    messages = lakebase.run_query(f"""
        SELECT message_id, ticket_id, message_text, author, created_at 
        FROM {MESSAGES_TABLE}
        WHERE ticket_id = %s
        ORDER BY created_at ASC
    """, (ticket_id,))
    
    return jsonify(messages)


@app.route("/api/tickets/<ticket_id>/messages", methods=["POST"])
def add_message(ticket_id):
    """Add a new message to a ticket."""
    data = request.json
    message_text = data.get("message", "").strip()
    
    if not message_text:
        return jsonify({"error": "Message is required"}), 400
    
    user_email = _current_user_email()
    author_name = user_email.split('@')[0].title()
    
    # Insert message using existing schema
    message_id = generate_message_id()
    lakebase.run_write(f"""
        INSERT INTO {MESSAGES_TABLE}
        (message_id, ticket_id, message_text, author, created_at)
        VALUES (%s, %s, %s, %s, now())
    """, (message_id, ticket_id, message_text, user_email))
    
    return jsonify({"success": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
