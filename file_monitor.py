import os
import time
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime
import json
import logging
from collections import defaultdict

# ✅
MAILGUN_API_KEY = "320690068d6b18741d8abd1af4d85a0c-ac3d5f74-f06a6839"

# ✅
MAILGUN_DOMAIN = "sandboxa3628d82a4714395ba7eeea5179f413c.mailgun.org"

# ✅
TO_EMAIL = "atharvkulkarni2002@gmail.com"

# ✅
FROM_EMAIL = f"no-reply@{MAILGUN_DOMAIN}"

# Watch these folders
WATCH_FOLDER = r"confidential"
DESTINATION_FOLDER = r"destination"


def send_email_notification(file_path, action, username=None, alert_id=None):
    """Send email via Mailgun when a file is copied or moved."""
    print(f"📧 Sending email for: {file_path} ({action})")

    try:
        email_html = f"""<!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>DLP Security Alert</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="border: 1px solid #ddd; border-radius: 5px; padding: 20px; background-color: #f9f9f9;">
                <h2 style="color: #c00;">DLP Security Alert</h2>
                <p>A security event has occurred in your DLP system:</p>
                <ul>
                    <li><strong>Action:</strong> {action}</li>
                    <li><strong>File:</strong> {file_path}</li>
                    <li><strong>User:</strong> {username or 'Unknown'}</li>
                </ul>
                <p>Please log in to your DLP admin dashboard to take appropriate action.</p>
                <p style="font-size: 12px; color: #777; margin-top: 30px;">This is an automated message from your DLP system.</p>
            </div>
        </body>
        </html>"""

        email_text = f"""
Security Alert from DLP System

Action: {action}
File: {file_path}
User: {username or 'Unknown'}

Please log in to your DLP admin dashboard to take appropriate action.

This is an automated message from your DLP system.
        """

        response = requests.post(
            f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
            auth=("api", MAILGUN_API_KEY),
            data={
                "from": FROM_EMAIL,
                "to": TO_EMAIL,
                "subject": f"DLP Alert: File {action}",
                "text": email_text,
                "html": email_html,
                "o:tracking": "yes",
                "o:tracking-clicks": "htmlonly",
                "h:Content-Type": "text/html"
            }
        )

        # Debug: Check Mailgun response
        if response.status_code == 200:
            print("✅ Email sent successfully!")
            print(f"Response: {response.text}")
            return True
        else:
            raise Exception(f"Mailgun API error: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"❌ Failed to send email: {str(e)}")
        logging.error(f"Failed to send email notification: {str(e)}")
        return False


class FileEventHandler(FileSystemEventHandler):
    def on_moved(self, event):
        """Triggered when a file is moved to another folder."""
        if event.is_directory:
            return
        print(f"📂 File moved: {event.src_path} → {event.dest_path}")
        if event.dest_path.startswith(DESTINATION_FOLDER):
            send_email_notification(event.dest_path, "moved")

    def on_created(self, event):
        """Triggered when a new file appears in the destination folder (copied)."""
        if event.is_directory:
            return
        print(f"📂 File copied : {event.src_path}")
        if event.src_path.startswith(DESTINATION_FOLDER):
            send_email_notification(event.src_path, "copied")


class FileMonitor(FileSystemEventHandler):
    def __init__(self, monitored_path="confidential"):
        self.monitored_path = monitored_path
        self.observer = Observer()
        self.user_actions = defaultdict(list)
        self.active_sessions = {}
        self.max_actions_per_user = 1000


        self.logger = logging.getLogger("file_monitor")
        handler = logging.FileHandler("logs/file_monitor.log")
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

        self.alerts = []
        self.alert_handlers = {}
        self.current_users = {}
        self.alert_levels = {"critical": 1, "warning": 2, "info": 3}
        self.file_transfers = []
        self.file_modifications = defaultdict(list)
        self.monitored_folders = set([monitored_path])

    def start(self):
        self.observer.schedule(self, self.monitored_path, recursive=True)
        self.observer.start()
        self.logger.info(f"File monitoring started for: {self.monitored_path}")

    def stop(self):
        self.observer.stop()
        self.observer.join()
        self.logger.info("File monitoring stopped")

    def log_action(self, username, action, filepath, status="success"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        action_data = {
            "timestamp": timestamp,
            "action": action,
            "filepath": str(filepath),
            "status": status,
        }

        # Implement circular buffer for actions
        actions = self.user_actions[username]
        actions.append(action_data)
        if len(actions) > self.max_actions_per_user:
            actions.pop(0)  # Remove oldest action

        self.logger.info(f"User {username}: {action} - {filepath} ({status})")

    def get_user_actions(self, username, limit=50):
        """Get most recent user actions with a limit"""
        actions = self.user_actions.get(username, [])
        return actions[-limit:]

    def get_all_actions(self):
        return dict(self.user_actions)

    def clear_user_actions(self, username):
        if username in self.user_actions:
            self.user_actions[username] = []

    def register_session(self, username, session_id):
        session_id_str = str(id(session_id))
        self.active_sessions[username] = {
            "session_id": session_id_str,
            "start_time": datetime.now(),
            "status": "active",
            "ip_address": "127.0.0.1",
        }
        self.logger.info(f"Session registered for user: {username}")

    def end_session(self, username):
        if username in self.active_sessions:
            self.active_sessions[username]["status"] = "terminated"
            self.active_sessions[username]["end_time"] = datetime.now()

    def get_active_sessions(self):
        """Get active sessions with clean serializable data"""
        active_sessions = {}
        for user, data in self.active_sessions.items():
            if data["status"] == "active":
                session_data = {
                    "session_id": data["session_id"],
                    "start_time": data["start_time"].strftime("%Y-%m-%d %H:%M:%S"),
                    "status": data["status"],
                    "ip_address": data["ip_address"],
                }
                active_sessions[user] = session_data
        return active_sessions

    def register_alert_handler(self, event_type, handler):
        self.alert_handlers[event_type] = handler

    def add_alert(
        self, alert_type, message, username=None, filepath=None, severity="warning"
    ):
        alert = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": alert_type,
            "message": message,
            "username": username,
            "filepath": filepath,
            "severity": severity,
            "handled": False,
        }
        self.alerts.append(alert)
        self.logger.warning(f"Alert: {message} ({severity})")

        if alert_type in self.alert_handlers:
            self.alert_handlers[alert_type](alert)

    def get_alerts(self, limit=50, include_handled=False):
        if include_handled:
            return self.alerts[-limit:]
        return [alert for alert in self.alerts if not alert["handled"]][-limit:]

    def mark_alert_handled(self, alert_index):
        if 0 <= alert_index < len(self.alerts):
            self.alerts[alert_index]["handled"] = True
            return True
        return False

    def set_current_user(self, username):
        self.current_users[os.getpid()] = username

    def get_current_user(self):
        return self.current_users.get(os.getpid())

    def add_monitored_folder(self, folder_path):
        if os.path.exists(folder_path):
            self.monitored_folders.add(folder_path)
            self.observer.schedule(self, folder_path, recursive=True)
            self.logger.info(f"Added folder to monitoring: {folder_path}")
            return True
        return False

    def get_monitored_folders(self):
        return list(self.monitored_folders)

    def track_file_transfer(self, source, destination, username):
        transfer = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": source,
            "destination": destination,
            "username": username,
        }
        self.file_transfers.append(transfer)
        self.logger.info(
            f"File transfer tracked: {source} -> {destination} by {username}"
        )

    def get_file_transfers(self, limit=50):
        return self.file_transfers[-limit:]

    def track_modification(self, filename, modification_type, username):
        """Track file modifications (still used by file monitoring notifications)"""
        modification = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": modification_type,
            "username": username,
        }
        self.file_modifications[filename].append(modification)
        # Keep only last 50 modifications per file
        if len(self.file_modifications[filename]) > 50:
            self.file_modifications[filename].pop(0)

    def get_file_modifications(self, filename):
        return self.file_modifications.get(filename, [])

    def on_created(self, event):
        if event.is_directory:
            return

        username = self.get_current_user()
        self.logger.info(f"File created: {event.src_path} by {username}")

        if username:
            self.log_action(username, "create", event.src_path)
            # Alert for sensitive file creation
            if any(
                keyword in event.src_path.lower()
                for keyword in ["secret", "confidential", "private"]
            ):
                self.add_alert(
                    "file_creation",
                    f"Sensitive file created: {os.path.basename(event.src_path)}",
                    username=username,
                    filepath=event.src_path,
                    severity="warning",
                )

    def on_modified(self, event):
        if event.is_directory:
            return

        username = self.get_current_user()
        self.logger.info(f"File modified: {event.src_path} by {username}")

        if username:
            self.log_action(username, "modify", event.src_path)
            self.track_modification(event.src_path, "modify", username)
            self.add_alert(
                "file_modification",
                f"File modified: {os.path.basename(event.src_path)}",
                username=username,
                filepath=event.src_path,
                severity="warning",
            )

    def on_deleted(self, event):
        if event.is_directory:
            return

        username = self.get_current_user()
        self.logger.info(f"File deleted: {event.src_path} by {username}")

        if username:
            self.log_action(username, "delete", event.src_path)
            self.add_alert(
                "file_deletion",
                f"File deleted: {os.path.basename(event.src_path)}",
                username=username,
                filepath=event.src_path,
                severity="critical",
            )

    def on_moved(self, event):
        if event.is_directory:
            return

        username = self.get_current_user()
        self.logger.info(
            f"File moved/renamed: from {event.src_path} to {event.dest_path}"
        )

        if username:
            self.track_file_transfer(event.src_path, event.dest_path, username)
            self.log_action(username, "move", f"{event.src_path} -> {event.dest_path}")


if __name__ == "__main__":
    event_handler = FileEventHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_FOLDER, recursive=True)
    observer.schedule(
        event_handler, DESTINATION_FOLDER, recursive=True
    )  # Watching the destination folder
    observer.start()

    print(
        f"Monitoring {WATCH_FOLDER} and {DESTINATION_FOLDER} for file transfers..."
    )
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
