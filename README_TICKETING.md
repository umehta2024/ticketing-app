# Ticketing Support App

This folder contains **TWO SEPARATE APPS**:

## 1. Stock Watchlist App (Original)
- **Files**: `app.py`, `massive_client.py`
- **Config**: `app.yaml`
- **Purpose**: Track stock prices from Massive API

## 2. Ticketing Support App (NEW)
- **Files**: `app_tickets.py`, `templates/tickets.html`, `static/style.css`
- **Config**: `app_tickets.yaml`
- **Purpose**: Support ticket management system

---

## How to Switch Between Apps

To run the ticketing support app, you need to update `app.yaml`:

### Option 1: Manually edit app.yaml
Replace the content of `app.yaml` with the content of `app_tickets.yaml`:

```yaml
command:
  - "python"
  - "app_tickets.py"

env:
  - name: LAKEBASE_SECRET_SCOPE
    value: "database"
  - name: LAKEBASE_SECRET_KEY
    value: "lakebase-url"
```

### Option 2: Rename files
```bash
# Backup the stock app config
mv app.yaml app_stock.yaml

# Use the ticketing app config
mv app_tickets.yaml app.yaml
```

---

## Ticketing App Structure

```
ticket-app/
├── app_tickets.py          # Flask backend for ticketing
├── app_tickets.yaml        # Configuration for ticketing app
├── lakebase.py             # Database helper (shared)
├── requirements.txt        # Python dependencies (shared)
├── static/
│   └── style.css          # Modern CSS styling
├── templates/
│   └── tickets.html       # Main UI
└── README_TICKETING.md    # This file
```

---

## Features

* **View All Tickets** - List with status badges, filtering, and search
* **Create New Tickets** - Modal form with title, description, and priority
* **Ticket Details** - Full view with message thread
* **Status Management** - Update ticket status (Open → In Progress → Closed)
* **Message Replies** - Add messages to any ticket
* **User Context** - Automatically tracks logged-in user via Databricks Auth
* **Modern UI** - Two-column layout with purple gradient theme
* **Responsive Design** - Works on desktop, tablet, and mobile

---

## Database Tables

The app creates two Lakebase (Postgres) tables:

### `support_tickets`
- `id` (serial primary key)
- `ticket_id` (unique, e.g., "TKT-1001")
- `title`
- `description`
- `status` (open, in-progress, closed)
- `priority` (low, medium, high)
- `requester_email`
- `assigned_to`
- `created_at`, `updated_at`

### `ticket_messages`
- `id` (serial primary key)
- `ticket_id` (foreign key)
- `author_email`
- `author_name`
- `message`
- `is_internal`
- `created_at`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Main UI |
| GET | `/api/tickets` | List all tickets |
| POST | `/api/tickets` | Create new ticket |
| GET | `/api/tickets/<id>` | Get ticket details |
| PATCH | `/api/tickets/<id>` | Update ticket status |
| GET | `/api/tickets/<id>/messages` | Get ticket messages |
| POST | `/api/tickets/<id>/messages` | Add message to ticket |

---

## Deployment Steps

1. **Update app.yaml** (see "How to Switch" above)
2. **Check app status**: `databricks apps get ticketing-app --output JSON`
3. **If STOPPED, start it**: `databricks apps start ticketing-app --timeout 20m`
4. **Deploy**: `databricks apps deploy ticketing-app --source-code-path /Workspace/Users/um2024@nyu.edu/ticketing-app`
5. **Open the app** at the URL shown in the deployment output

---

## Technology Stack

* **Backend**: Flask (Python 3.11)
* **Database**: Lakebase (Databricks-managed Postgres)
* **Frontend**: Vanilla JavaScript + HTML + CSS
* **Auth**: Databricks Apps built-in user context
* **Styling**: Custom CSS with gradient theme

---

## Next Steps

You can enhance the app with:
* Email notifications when tickets are updated
* File attachments to tickets
* Ticket assignment to support agents
* SLA tracking and escalation
* Analytics dashboard for ticket metrics
* Search functionality across tickets
* Tags and categories
* Custom fields per ticket type