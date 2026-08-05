#!/usr/bin/env python3
"""
Lakebase Secret Setup Script

This script helps you configure the Lakebase connection URL as a Databricks secret.
The ticketing app uses this secret to connect to your Postgres database.

Usage:
    python setup_secrets.py
    
Or import and use the functions:
    from setup_secrets import set_lakebase_url, get_lakebase_url, test_connection
"""

import base64
import sys
from databricks.sdk import WorkspaceClient

# Default configuration
DEFAULT_SCOPE = "database"
DEFAULT_KEY = "lakebase-url"


def set_lakebase_url(url: str, scope: str = DEFAULT_SCOPE, key: str = DEFAULT_KEY):
    """
    Store a Lakebase connection URL as a Databricks secret.
    
    Args:
        url: Postgres connection URL, format:
             postgresql://username:password@host:port/database?sslmode=require
        scope: Secret scope name (default: 'database')
        key: Secret key name (default: 'lakebase-url')
    
    Example:
        set_lakebase_url(
            "postgresql://user:pass@host.databricks.com:5432/ticketing_system?sslmode=require"
        )
    """
    w = WorkspaceClient()
    
    # Validate URL format
    if not url.startswith("postgresql://"):
        raise ValueError("URL must start with 'postgresql://'")
    
    try:
        # Create scope if it doesn't exist
        try:
            w.secrets.create_scope(scope=scope)
            print(f"✅ Created secret scope '{scope}'")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"ℹ️  Secret scope '{scope}' already exists")
            else:
                raise
        
        # Store the secret - SDK will base64 encode it automatically
        w.secrets.put_secret(
            scope=scope,
            key=key,
            string_value=url
        )
        
        print(f"✅ Secret '{scope}/{key}' updated successfully!")
        print(f"\n📝 Connection details (password hidden):")
        
        # Show connection info (hide password)
        import re
        match = re.match(r'postgresql://([^:]+):([^@]+)@([^/]+)/(.+)', url)
        if match:
            user, password, host, db = match.groups()
            print(f"   User: {user}")
            print(f"   Host: {host}")
            print(f"   Database: {db.split('?')[0]}")
            print(f"   Password: {'*' * len(password)} (hidden)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting secret: {e}")
        return False


def get_lakebase_url(scope: str = DEFAULT_SCOPE, key: str = DEFAULT_KEY) -> str:
    """
    Retrieve and decode the Lakebase connection URL from secrets.
    
    Args:
        scope: Secret scope name (default: 'database')
        key: Secret key name (default: 'lakebase-url')
    
    Returns:
        The decoded Postgres connection URL
    """
    w = WorkspaceClient()
    
    try:
        secret = w.secrets.get_secret(scope=scope, key=key)
        # SDK returns base64-encoded value, we need to decode it
        url = base64.b64decode(secret.value).decode('utf-8')
        return url
    except Exception as e:
        print(f"❌ Error reading secret: {e}")
        return None


def test_connection(scope: str = DEFAULT_SCOPE, key: str = DEFAULT_KEY) -> bool:
    """
    Test the Lakebase connection using the stored secret.
    
    Args:
        scope: Secret scope name
        key: Secret key name
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        import psycopg2
    except ImportError:
        print("❌ psycopg2 not installed. Run: pip install psycopg2-binary")
        return False
    
    url = get_lakebase_url(scope, key)
    if not url:
        return False
    
    try:
        print("🔌 Testing connection...")
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        
        # Get database version
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        
        # Get current database
        cur.execute("SELECT current_database()")
        database = cur.fetchone()[0]
        
        # List tables
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]
        
        conn.close()
        
        print("✅ Connection successful!\n")
        print(f"📊 Database: {database}")
        print(f"📦 PostgreSQL: {version.split(',')[0]}")
        print(f"\n📋 Tables ({len(tables)}):")
        for table in tables:
            marker = " ✓" if table in ['tickets', 'ticket_messages'] else ""
            print(f"   - {table}{marker}")
        
        # Check if ticketing tables exist
        has_tickets = 'tickets' in tables
        has_messages = 'ticket_messages' in tables
        
        if has_tickets and has_messages:
            print("\n✅ Ticketing tables are ready!")
        else:
            print("\n⚠️  Ticketing tables not found. Run the app to create them.")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


def interactive_setup():
    """
    Interactive command-line setup wizard.
    """
    print("="*60)
    print("🔧 Lakebase Secret Setup for Ticketing App")
    print("="*60)
    print()
    
    # Check if secret already exists
    existing_url = get_lakebase_url()
    if existing_url:
        print("ℹ️  A Lakebase secret is already configured.")
        print("\nCurrent connection:")
        import re
        match = re.match(r'postgresql://([^:]+):([^@]+)@([^/]+)/(.+)', existing_url)
        if match:
            user, password, host, db = match.groups()
            print(f"   Database: {db.split('?')[0]}")
            print(f"   Host: {host}")
            print(f"   User: {user}")
        print()
        
        response = input("Do you want to update it? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print("\n✅ Keeping existing secret.")
            return
    
    print("\n📝 Enter your Lakebase connection details:\n")
    
    # Get connection details
    host = input("Host (e.g., ep-xxx.database.us-east-2.cloud.databricks.com): ")
    port = input("Port [5432]: ").strip() or "5432"
    database = input("Database name (e.g., ticketing_system): ")
    username = input("Username: ")
    password = input("Password: ")
    
    # Build URL
    url = f"postgresql://{username}:{password}@{host}:{port}/{database}?sslmode=require"
    
    print("\n🔐 Storing secret...")
    success = set_lakebase_url(url)
    
    if success:
        print("\n🧪 Testing connection...")
        test_connection()
        print("\n✅ Setup complete! Your ticketing app is ready to deploy.")
    else:
        print("\n❌ Setup failed. Please check your credentials and try again.")


def main():
    """
    Main entry point for command-line usage.
    """
    if len(sys.argv) > 1:
        # If URL provided as argument
        url = sys.argv[1]
        print(f"Setting Lakebase URL from command line...")
        success = set_lakebase_url(url)
        if success:
            test_connection()
    else:
        # Interactive mode
        interactive_setup()


if __name__ == "__main__":
    main()