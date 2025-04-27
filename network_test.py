import time
import os
import json
import requests
import sys
from datetime import datetime
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

# ✅ Mailgun API Credentials
MAILGUN_API_KEY = "320690068d6b18741d8abd1af4d85a0c-ac3d5f74-f06a6839"
MAILGUN_DOMAIN = "sandboxa3628d82a4714395ba7eeea5179f413c.mailgun.org"
TO_EMAIL = "srivastava.daksh89@gmail.com"

# ✅ Log file paths
LOG_FILE = "logs/drive_monitor_log.txt"
BACKUP_LOG_FILE = "logs/drive_monitor_log_backup.txt"
MAX_LOG_SIZE = 5 * 1024 * 1024  # 🔹 5MB Limit

# ✅ Get formatted timestamp
def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ✅ Manage log file size
def manage_log_file():
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_SIZE:
        if os.path.exists(BACKUP_LOG_FILE):
            os.remove(BACKUP_LOG_FILE)
        os.rename(LOG_FILE, BACKUP_LOG_FILE)

# ✅ Log activity
def log_activity(message):
    manage_log_file()  # 🔹 Check file size before logging
    timestamp = get_timestamp()
    log_entry = f"[{timestamp}] {message}\n"
    
    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(log_entry)
    
    print(log_entry.strip())

# ✅ Send email alert with drive details
def send_email_alert(message, drive_user):
    full_message = f"🔍 Google Drive User: {drive_user['name']} ({drive_user['email']})\n\n{message}"
    return requests.post(
        f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
        auth=("api", MAILGUN_API_KEY),
        data={"from": f"Drive Monitor <monitor@{MAILGUN_DOMAIN}>",
              "to": [TO_EMAIL],
              "subject": "Google Drive Activity Alert",
              "text": full_message}
    )

# ✅ Authenticate Google Drive & Get User Info
def authenticate_drive():
    gauth = GoogleAuth()
    gauth.LocalWebserverAuth()  # Opens browser for authentication
    drive = GoogleDrive(gauth)

    # Get account details
    about = drive.GetAbout()
    user_name = about["user"]["displayName"]
    user_email = about["user"]["emailAddress"]

    drive_user = {"name": user_name, "email": user_email}

    log_activity(f"🔍 Monitoring Google Drive of: {user_name} ({user_email})")
    send_email_alert(f"✅ Monitoring Started!", drive_user)

    return drive, drive_user

drive, drive_user = authenticate_drive()

# Get initial file list from Google Drive
def get_drive_files():
    file_dict = {}
    file_list = drive.ListFile({'q': "'root' in parents and trashed=false"}).GetList()
    
    for file in file_list:
        file_dict[file['id']] = {
            'title': file['title'],
            'modifiedDate': file['modifiedDate']
        }
    return file_dict

# Monitor Google Drive Changes
def monitor_google_drive():
    prev_files = get_drive_files()

    try:
        while True:
            time.sleep(10)
            current_files = get_drive_files()

            # Check for new files
            for file_id, file_info in current_files.items():
                if file_id not in prev_files:
                    message = f"📄 New File Created: {file_info['title']} at {get_timestamp()}"
                    log_activity(message)
                    send_email_alert(message, drive_user)

            # Check for modified files
            for file_id, file_info in current_files.items():
                if file_id in prev_files and file_info['modifiedDate'] != prev_files[file_id]['modifiedDate']:
                    message = f"✏️ File Modified: {file_info['title']} at {get_timestamp()}"
                    log_activity(message)
                    send_email_alert(message, drive_user)

            # Check for deleted files
            for file_id, file_info in prev_files.items():
                if file_id not in current_files:
                    message = f"❌ File Deleted: {file_info['title']} at {get_timestamp()}"
                    log_activity(message)
                    send_email_alert(message, drive_user)

            prev_files = current_files

    except KeyboardInterrupt:
        log_activity("🛑 Monitoring stopped by user.")
        send_email_alert("🛑 Monitoring Stopped!", drive_user)
        sys.exit(0)

if __name__ == "__main__":
    monitor_google_drive()