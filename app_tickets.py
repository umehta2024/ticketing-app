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

# Table names
TICKETS_TABLE = "support_tickets"
MESSAGES_TABLE = "ticket_messages"


def _current_user_email() -> str:
    """Get the current logged-in user's email."""
    header_email = request.headers.get("X-Forwarded-Email")
    if header_email:
        return header_email
    return _w.current_user.me().user_name


def ensure_tables():
    """Create the tickets and messages tables if they don't exist."""
    # Create tickets table
    lakebase.run_write(f"""
        CREATE TABLE IF NOT EXISTS {TICKETS_TABLE} (
            id SERIAL PRIMARY KEY,
            ticket_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            priority TEXT DEFAULT 'medium',
            requester_email TEXT NOT NULL,
            assigned_to TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    
    # Create messages table
    lakebase.run_write(f"""
        CREATE TABLE IF NOT EXISTS {MESSAGES_TABLE} (
            id SERIAL PRIMARY KEY,
            ticket_id TEXT NOT NULL,
            author_email TEXT NOT NULL,
            author_name TEXT NOT NULL,
            message TEXT NOT NULL,
            is_internal BOOLEAN DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            FOREIGN KEY (ticket_id) REFERENCES {TICKETS_TABLE}(ticket_id) ON DELETE CASCADE
        )
    """)
    
    # Create indexes
    lakebase.run_write(f"""
        CREATE INDEX IF NOT EXISTS idx_tickets_requester 
        ON {TICKETS_TABLE}(requester_email)
    """)
    
    lakebase.run_write(f"""
        CREATE INDEX IF NOT EXISTS idx_tickets_status 
        ON {TICKETS_TABLE}(status)
    """)
    
    lakebase.run_write(f"""
        CREATE INDEX IF NOT EXISTS idx_messages_ticket 
        ON {MESSAGES_TABLE}(ticket_id)
    """)


def generate_ticket_id() -> str:
    """Generate a unique ticket ID like TKT-1001."""
    result = lakebase.run_query(
        f"SELECT MAX(id) as max_id FROM {TICKETS_TABLE}"
    )
    max_id = result[0].get('max_id') or 0
    return f"TKT-{1000 + max_id + 1}"


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
            SELECT * FROM {TICKETS_TABLE}
            WHERE status = %s
            ORDER BY updated_at DESC
        """, (status_filter,))
    else:
        tickets = lakebase.run_query(f"""
            SELECT * FROM {TICKETS_TABLE}
            ORDER BY updated_at DESC
        """)
    
    return jsonify(tickets)


@app.route("/api/tickets", methods=["POST"])
def create_ticket():
    """Create a new support ticket."""
    data = request.json
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    priority = data.get("priority", "medium")
    
    if not title:
        return jsonify({"error": "Title is required"}), 400
    
    user_email = _current_user_email()
    ticket_id = generate_ticket_id()
    
    lakebase.run_write(f"""
        INSERT INTO {TICKETS_TABLE} 
        (ticket_id, title, description, priority, requester_email, status)
        VALUES (%s, %s, %s, %s, %s, 'open')
    """, (ticket_id, title, description, priority, user_email))
    
    # Add initial message
    author_name = user_email.split('@')[0].title()
    lakebase.run_write(f"""
        INSERT INTO {MESSAGES_TABLE}
        (ticket_id, author_email, author_name, message)
        VALUES (%s, %s, %s, %s)
    """, (ticket_id, user_email, author_name, description or "Ticket created"))
    
    return jsonify({
        "ticket_id": ticket_id,
        "title": title,
        "status": "open"
    })


@app.route("/api/tickets/<ticket_id>", methods=["GET"])
def get_ticket(ticket_id):
    """Get a specific ticket with its details."""
    tickets = lakebase.run_query(f"""
        SELECT * FROM {TICKETS_TABLE}
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
            SET status = %s, updated_at = now()
            WHERE ticket_id = %s
        """, (status, ticket_id))
    
    return jsonify({"ticket_id": ticket_id, "status": status})


@app.route("/api/tickets/<ticket_id>/messages", methods=["GET"])
def get_messages(ticket_id):
    """Get all messages for a ticket."""
    messages = lakebase.run_query(f"""
        SELECT * FROM {MESSAGES_TABLE}
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
    
    lakebase.run_write(f"""
        INSERT INTO {MESSAGES_TABLE}
        (ticket_id, author_email, author_name, message)
        VALUES (%s, %s, %s, %s)
    """, (ticket_id, user_email, author_name, message_text))
    
    # Update ticket's updated_at timestamp
    lakebase.run_write(f"""
        UPDATE {TICKETS_TABLE}
        SET updated_at = now()
        WHERE ticket_id = %s
    """, (ticket_id,))
    
    return jsonify({"success": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)