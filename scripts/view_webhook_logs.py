"""
View webhook logs for debugging.

Usage:
    modal run scripts/view_webhook_logs.py::list_webhooks [--limit N]
    modal run scripts/view_webhook_logs.py::view_webhook --log-id N
    modal run scripts/view_webhook_logs.py::view_latest
"""

import modal
import json
from src.database import Database

app = modal.App("webhook-log-viewer")

# Create image with dependencies
image = modal.Image.debian_slim().add_local_file(
    "src/database.py", "/root/src/database.py"
)

# Use production volume by default (can be overridden with --env dev)
volume = modal.Volume.from_name("story-data", create_if_missing=False)


@app.function(image=image, volumes={"/data": volume})
def list_webhooks(limit: int = 20):
    """List recent webhook logs."""
    db = Database("/data/stories.db")
    logs = db.get_webhook_logs(limit=limit)

    print("=" * 100)
    print(f"WEBHOOK LOGS (showing {len(logs)} most recent)")
    print("=" * 100)

    if not logs:
        print("📭 No webhook logs found")
        return

    for log in logs:
        print(f"\nLog ID: {log['id']}")
        print(f"  Received: {log['received_at']}")
        print(f"  Status: {log['processing_status']}")
        print(f"  Emails parsed: {log['parsed_emails_count'] or 0}")
        if log['story_ids']:
            print(f"  Story IDs: {log['story_ids']}")
        if log['error_message']:
            print(f"  ❌ Error: {log['error_message']}")

        # Show payload preview
        payload = log['raw_payload']
        if len(payload) > 200:
            print(f"  Payload preview: {payload[:200]}...")
        else:
            print(f"  Payload: {payload}")

    print("\n" + "=" * 100)
    print(f"To view full webhook payload: modal run scripts/view_webhook_logs.py::view_webhook --log-id N")


@app.function(image=image, volumes={"/data": volume})
def view_webhook(log_id: int):
    """View a specific webhook log in detail."""
    db = Database("/data/stories.db")
    log = db.get_webhook_log_by_id(log_id)

    if not log:
        print(f"❌ Webhook log {log_id} not found")
        return

    print("=" * 100)
    print(f"WEBHOOK LOG #{log['id']}")
    print("=" * 100)
    print(f"Received: {log['received_at']}")
    print(f"Status: {log['processing_status']}")
    print(f"Emails parsed: {log['parsed_emails_count'] or 0}")
    if log['story_ids']:
        print(f"Story IDs: {log['story_ids']}")
    if log['error_message']:
        print(f"\n❌ Error: {log['error_message']}")

    print("\n" + "-" * 100)
    print("RAW PAYLOAD:")
    print("-" * 100)

    try:
        # Try to pretty-print as JSON
        payload_dict = json.loads(log['raw_payload'])
        print(json.dumps(payload_dict, indent=2))
    except json.JSONDecodeError:
        # Fall back to raw text
        print(log['raw_payload'])

    print("\n" + "=" * 100)


@app.function(image=image, volumes={"/data": volume})
def view_latest():
    """View the most recent webhook log."""
    db = Database("/data/stories.db")
    logs = db.get_webhook_logs(limit=1)

    if not logs:
        print("📭 No webhook logs found")
        return

    log = logs[0]
    print("=" * 100)
    print("LATEST WEBHOOK LOG")
    print("=" * 100)
    print(f"Log ID: {log['id']}")
    print(f"Received: {log['received_at']}")
    print(f"Status: {log['processing_status']}")
    print(f"Emails parsed: {log['parsed_emails_count'] or 0}")
    if log['story_ids']:
        print(f"Story IDs: {log['story_ids']}")
    if log['error_message']:
        print(f"\n❌ Error: {log['error_message']}")

    print("\n" + "-" * 100)
    print("RAW PAYLOAD:")
    print("-" * 100)

    try:
        # Try to pretty-print as JSON
        payload_dict = json.loads(log['raw_payload'])
        print(json.dumps(payload_dict, indent=2))
    except json.JSONDecodeError:
        # Fall back to raw text
        print(log['raw_payload'])

    print("\n" + "=" * 100)


# Dev environment versions
app_dev = modal.App("webhook-log-viewer-dev")
volume_dev = modal.Volume.from_name("story-data-dev", create_if_missing=False)


@app_dev.function(image=image, volumes={"/data": volume_dev})
def list_webhooks_dev(limit: int = 20):
    """List recent webhook logs (dev environment)."""
    db = Database("/data/stories-dev.db")
    logs = db.get_webhook_logs(limit=limit)

    print("=" * 100)
    print(f"DEV WEBHOOK LOGS (showing {len(logs)} most recent)")
    print("=" * 100)

    if not logs:
        print("📭 No webhook logs found in dev database")
        return

    for log in logs:
        print(f"\nLog ID: {log['id']}")
        print(f"  Received: {log['received_at']}")
        print(f"  Status: {log['processing_status']}")
        print(f"  Emails parsed: {log['parsed_emails_count'] or 0}")
        if log['story_ids']:
            print(f"  Story IDs: {log['story_ids']}")
        if log['error_message']:
            print(f"  ❌ Error: {log['error_message']}")

        # Show payload preview
        payload = log['raw_payload']
        if len(payload) > 200:
            print(f"  Payload preview: {payload[:200]}...")
        else:
            print(f"  Payload: {payload}")

    print("\n" + "=" * 100)
    print(f"To view full webhook payload: modal run scripts/view_webhook_logs.py::view_webhook_dev --log-id N")


@app_dev.function(image=image, volumes={"/data": volume_dev})
def view_webhook_dev(log_id: int):
    """View a specific webhook log (dev environment)."""
    db = Database("/data/stories-dev.db")
    log = db.get_webhook_log_by_id(log_id)

    if not log:
        print(f"❌ Webhook log {log_id} not found in dev database")
        return

    print("=" * 100)
    print(f"DEV WEBHOOK LOG #{log['id']}")
    print("=" * 100)
    print(f"Received: {log['received_at']}")
    print(f"Status: {log['processing_status']}")
    print(f"Emails parsed: {log['parsed_emails_count'] or 0}")
    if log['story_ids']:
        print(f"Story IDs: {log['story_ids']}")
    if log['error_message']:
        print(f"\n❌ Error: {log['error_message']}")

    print("\n" + "-" * 100)
    print("RAW PAYLOAD:")
    print("-" * 100)

    try:
        # Try to pretty-print as JSON
        payload_dict = json.loads(log['raw_payload'])
        print(json.dumps(payload_dict, indent=2))
    except json.JSONDecodeError:
        # Fall back to raw text
        print(log['raw_payload'])

    print("\n" + "=" * 100)
