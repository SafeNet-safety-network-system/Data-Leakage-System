import streamlit as st
import os
import time
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import threading
import json
from pathlib import Path
import socket

from user_socket_client import UserClient
from utils import setup_logging, check_file_encryption_status
from port_monitor import PortMonitor, list_connected_usb_devices, list_available_ports, get_usb_drive_letters

# Setup logging
logger = setup_logging("dlp_streamlit")

# Initialize directories
if not os.path.exists("confidential"):
    os.makedirs("confidential")
    logger.info("Created confidential directory")

if not os.path.exists("logs"):
    os.makedirs("logs")
    logger.info("Created logs directory")

# Check if server is running
def is_server_running(host="localhost", port=5000):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect((host, port))
            return True
    except:
        return False

# Set page config
st.set_page_config(
    page_title="DLP System Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Server status check
server_running = is_server_running()
if not server_running:
    st.error("""
    ## ⚠️ DLP Server is not running
    
    The DLP server must be running before you can use this application.
    
    Please start the server by running this command in a terminal:
    ```
    python socket_server.py
    ```
    
    Then refresh this page.
    """)
    st.stop()

# Initialize session state variables
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'client' not in st.session_state:
    st.session_state.client = None
if 'user_type' not in st.session_state:
    st.session_state.user_type = None
if 'monitoring_active' not in st.session_state:
    st.session_state.monitoring_active = False
if 'monitor' not in st.session_state:
    st.session_state.monitor = None

# Styling
st.markdown("""
<style>
    .success-box {
        padding: 10px;
        background-color: #d4edda;
        color: #155724;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .error-box {
        padding: 10px;
        background-color: #f8d7da;
        color: #721c24;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .info-box {
        padding: 10px;
        background-color: #d1ecf1;
        color: #0c5460;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .warning-box {
        padding: 10px;
        background-color: #fff3cd;
        color: #856404;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .encrypted-file {
        color: #dc3545;
        font-weight: bold;
    }
    .status-indicator {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 5px;
    }
    .status-active {
        background-color: #28a745;
    }
    .status-inactive {
        background-color: #dc3545;
    }
    .file-card {
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 10px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

def success_message(message):
    st.markdown(f'<div class="success-box">{message}</div>', unsafe_allow_html=True)

def error_message(message):
    st.markdown(f'<div class="error-box">{message}</div>', unsafe_allow_html=True)

def info_message(message):
    st.markdown(f'<div class="info-box">{message}</div>', unsafe_allow_html=True)

def warning_message(message):
    st.markdown(f'<div class="warning-box">{message}</div>', unsafe_allow_html=True)

def login_page():
    st.title("DLP System Login")
    
    # Server status indicator
    server_status = "Online" if is_server_running() else "Offline"
    status_color = "green" if server_status == "Online" else "red"
    st.markdown(f"""
    <div style="margin-bottom: 20px;">
        <span style="color:{status_color}; font-weight:bold;">● Server Status: {server_status}</span>
    </div>
    """, unsafe_allow_html=True)
    
    if server_status == "Offline":
        st.error("""
        ## ⚠️ Server Connection Error
        
        The DLP server is not running. Please start the server before trying to log in.
        
        Run this command in a terminal:
        ```
        python socket_server.py
        ```
        """)
        return
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Admin Login")
        admin_username = st.text_input("Admin Username", key="admin_username")
        admin_password = st.text_input("Admin Password", type="password", key="admin_password")
        
        if st.button("Login as Admin"):
            if not admin_username or not admin_password:
                error_message("Username and password cannot be empty!")
            else:
                try:
                    client = UserClient()
                    login_result = client.admin_login(admin_username, admin_password)
                    
                    if login_result["status"] == "success":
                        st.session_state.logged_in = True
                        st.session_state.username = admin_username
                        st.session_state.client = client
                        st.session_state.user_type = "admin"
                        success_message(f"Welcome Admin {admin_username}!")
                        st.rerun()
                    else:
                        error_message("Invalid admin credentials!")
                except ConnectionRefusedError:
                    error_message("Could not connect to server. Please ensure the server is running.")
                except Exception as e:
                    error_message(f"Login error: {str(e)}")
    
    with col2:
        st.subheader("User Login")
        user_username = st.text_input("User Username", key="user_username")
        user_password = st.text_input("User Password", type="password", key="user_password")
        
        if st.button("Login as User"):
            if not user_username or not user_password:
                error_message("Username and password cannot be empty!")
            else:
                try:
                    client = UserClient()
                    if client.user_login(user_username, user_password):
                        st.session_state.logged_in = True
                        st.session_state.username = user_username
                        st.session_state.client = client
                        st.session_state.user_type = "user"
                        success_message(f"Welcome User {user_username}!")
                        st.rerun()
                    else:
                        error_message("Invalid user credentials!")
                except ConnectionRefusedError:
                    error_message("Could not connect to server. Please ensure the server is running.")
                except Exception as e:
                    error_message(f"Login error: {str(e)}")

def logout():
    if st.session_state.client:
        try:
            st.session_state.client.close()
        except:
            pass
    
    if st.session_state.monitor and getattr(st.session_state.monitor, 'running', False):
        st.session_state.monitor.stop_monitoring()
    
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.client = None
    st.session_state.user_type = None
    st.session_state.monitoring_active = False
    st.session_state.monitor = None
    st.rerun()

def view_files_page():
    st.subheader("Available Files")
    
    # Get files with encryption status
    try:
        files_with_status = st.session_state.client.list_files(include_encryption_status=True)
        
        if not files_with_status:
            info_message("No files found in the confidential directory.")
            return
        
        # Display files in a row-wise list
        for file_info in files_with_status:
            file = file_info["name"]
            is_encrypted = file_info["encrypted"]
            
            st.markdown(f"""
            <div class="file-card">
                <h3>{'🔒 ' if is_encrypted else '📄 '}{file}</h3>
                <p>Status: <span class="{'encrypted-file' if is_encrypted else ''}">
                    {'Encrypted' if is_encrypted else 'Unencrypted'}
                </span></p>
            </div>
            """, unsafe_allow_html=True)
    except Exception as e:
        error_message(f"Error retrieving files: {str(e)}")

def file_encryption_page():
    st.subheader("File Encryption Management")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Encrypt File", "Decrypt File", "Encryption Keys", "Access Requests"])
    
    with tab1:
        st.subheader("Encrypt File")
        
        try:
            if not st.session_state.client:
                error_message("Client is not initialized. Please ensure you are logged in and connected to the server.")
                return
            
            files = st.session_state.client.list_files()
            if not files:
                info_message("No files available to encrypt.")
                return
                
            # Format files as options with encryption status
            file_options = []
            for file in files:
                encrypted = check_file_encryption_status(file)
                status = " [ENCRYPTED]" if encrypted else ""
                file_options.append(f"{file}{status}")
                
            selected_file = st.selectbox("Select file to encrypt:", file_options)
            
            if st.button("Encrypt File"):
                # Extract filename without status
                filename = selected_file.split(" [ENCRYPTED]")[0]
                full_path = os.path.join("confidential", filename)
                
                if "[ENCRYPTED]" in selected_file:
                    warning_message("This file is already encrypted.")
                else:
                    key = st.session_state.client.encrypt_file(full_path)
                    if key:
                        success_message("File encrypted successfully!")
                        st.code(key, language="text")
                        st.info("Keep this key safe. You'll need it to decrypt the file.")
                    else:
                        error_message("Failed to encrypt file.")
        except Exception as e:
            error_message(f"Error: {str(e)}")
    
    with tab2:
        st.subheader("Decrypt File")
        
        try:
            files = st.session_state.client.list_files()
            if not files:
                info_message("No files available to decrypt.")
                return
            
            # Format files as options with encryption status
            file_options = []
            for file in files:
                encrypted = check_file_encryption_status(file)
                status = " [ENCRYPTED]" if encrypted else ""
                file_options.append(f"{file}{status}")
                
            selected_file = st.selectbox("Select file to decrypt:", file_options, key="decrypt_file")
            
            # Extract filename without status
            filename = selected_file.split(" [ENCRYPTED]")[0]
            
            decryption_key = st.text_input("Enter decryption key:", type="password")
            
            if st.button("Decrypt File"):
                if "[ENCRYPTED]" not in selected_file:
                    warning_message("This file is not encrypted.")
                else:
                    full_path = os.path.join("confidential", filename)
                    if st.session_state.client.decrypt_file(full_path, decryption_key):
                        success_message("File decrypted successfully!")
                    else:
                        error_message("Failed to decrypt file. Invalid key or corrupted file.")
        except Exception as e:
            error_message(f"Error: {str(e)}")
    
    with tab3:
        st.subheader("Encryption Keys")
        
        try:
            keys = st.session_state.client.get_keys()
            if not keys or len(keys) == 0:
                info_message("No encryption keys found.")
                return
                
            # Convert to DataFrame for better display
            key_data = []
            for filename, data in keys.items():
                if isinstance(data, dict) and "key" in data and "date" in data:
                    key_data.append({
                        "Filename": filename,
                        "Key": data['key'],
                        "Encryption Date": data['date']
                    })
            
            if key_data:
                df = pd.DataFrame(key_data)
                st.dataframe(df, use_container_width=True)
        except Exception as e:
            error_message(f"Error retrieving keys: {str(e)}")
    
    with tab4:
        st.subheader("Access Requests")
        
        try:
            pending = st.session_state.client.get_pending_requests()
            if not pending:
                info_message("No pending access requests.")
                return
                
            # Convert to DataFrame for better display
            request_data = []
            for i, req in enumerate(pending, 1):
                request_data.append({
                    "ID": i,
                    "Username": req['username'],
                    "Filename": req['filename']
                })
            
            df = pd.DataFrame(request_data)
            st.dataframe(df, use_container_width=True)
            
            # Approve request section
            st.subheader("Approve Request")
            request_id = st.number_input("Enter request ID to approve:", min_value=1, max_value=len(pending) if pending else 1, step=1)
            
            if st.button("Approve Request"):
                if 1 <= request_id <= len(pending):
                    req = pending[request_id - 1]
                    if st.session_state.client.approve_request(req["username"], req["filename"]):
                        success_message("Request approved successfully!")
                    else:
                        error_message("Failed to approve request.")
                else:
                    error_message("Invalid request ID.")
        except Exception as e:
            error_message(f"Error retrieving requests: {str(e)}")

def file_monitoring_page():
    st.subheader("File Monitoring")
    
    tab1, tab2, tab3 = st.tabs(["Monitored Folders", "Add Folder to Monitor", "File Transfers"])
    
    with tab1:
        st.subheader("Monitored Folders")
        
        # Show default folders first
        st.markdown("**Default Monitored Folders:**")
        st.markdown("- confidential (Source folder)")
        st.markdown("- destination (Target folder)")
        
        # Show additional monitored folders
        try:
            custom_folders = st.session_state.client.get_monitored_folders()
            if custom_folders:
                st.markdown("**Additional Monitored Folders:**")
                for folder in custom_folders:
                    st.markdown(f"- {folder}")
                    try:
                        if os.path.exists(folder):
                            files = os.listdir(folder)
                            for file in files:
                                st.markdown(f"  -- {file}")
                    except Exception as e:
                        st.markdown(f"  - Error accessing folder: {str(e)}")
        except Exception as e:
            error_message(f"Error: {str(e)}")
    
    with tab2:
        st.subheader("Add New Folder to Monitor")
        folder_path = st.text_input("Enter full folder path:")
        
        if st.button("Add Folder"):
            if not folder_path:
                error_message("Invalid folder path")
            elif not os.path.exists(folder_path):
                create = st.checkbox("Folder doesn't exist. Create it?")
                if create:
                    try:
                        os.makedirs(folder_path)
                        if st.session_state.client.add_monitored_folder(folder_path):
                            success_message(f"Successfully added {folder_path} to monitored folders")
                        else:
                            error_message("Failed to add folder to monitoring list")
                    except Exception as e:
                        error_message(f"Error creating folder: {str(e)}")
            else:
                if st.session_state.client.add_monitored_folder(folder_path):
                    success_message(f"Successfully added {folder_path} to monitored folders")
                else:
                    error_message("Failed to add folder to monitoring list")
    
    with tab3:
        st.subheader("File Transfer History")
        
        try:
            transfers = st.session_state.client.get_file_transfers()
            if not transfers:
                info_message("No file transfers have been recorded")
                return
                
            # Convert to DataFrame for better display
            transfer_data = []
            for transfer in transfers:
                transfer_data.append({
                    "Timestamp": transfer['timestamp'],
                    "Source": transfer['source'],
                    "Destination": transfer['destination'],
                    "User": transfer['username']
                })
            
            df = pd.DataFrame(transfer_data)
            st.dataframe(df, use_container_width=True)
            
            # Visualization
            if len(transfer_data) > 0:
                st.subheader("Transfer Activity by User")
                user_counts = df['User'].value_counts()
                fig, ax = plt.subplots()
                user_counts.plot(kind='bar', ax=ax)
                st.pyplot(fig)
        except Exception as e:
            error_message(f"Error retrieving transfers: {str(e)}")

def usb_monitoring_page():
    st.subheader("External Device Monitoring")
    
    tab1, tab2, tab3 = st.tabs(["USB Monitoring", "Connected Devices", "USB Alerts"])
    
    with tab1:
        st.subheader("USB Port Monitoring")
        
        # Initialize monitoring status
        if 'monitor' not in st.session_state:
            st.session_state.monitor = PortMonitor()
        
        # Display monitoring status
        monitoring_status = getattr(st.session_state.monitor, 'running', False)
        status_color = "status-active" if monitoring_status else "status-inactive"
        st.markdown(f"""
        <div>
            <span class="status-indicator {status_color}"></span>
            <span>Monitoring Status: {'Active' if monitoring_status else 'Inactive'}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Start/Stop buttons
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Start Monitoring", disabled=monitoring_status):
                try:
                    # Start in a non-blocking thread
                    if not monitoring_status:
                        st.session_state.monitor = PortMonitor()
                        monitor_thread = threading.Thread(
                            target=st.session_state.monitor.start_monitoring,
                            args=(False,),  # No automatic email notifications
                            daemon=True
                        )
                        monitor_thread.start()
                        st.session_state.monitoring_active = True
                        success_message("USB port monitoring started")
                        time.sleep(1)  # Give the thread time to start
                        st.rerun()
                except Exception as e:
                    error_message(f"Error starting monitoring: {str(e)}")
        
        with col2:
            if st.button("Stop Monitoring", disabled=not monitoring_status):
                try:
                    if monitoring_status:
                        st.session_state.monitor.stop_monitoring()
                        st.session_state.monitoring_active = False
                        success_message("USB port monitoring stopped")
                        st.rerun()
                except Exception as e:
                    error_message(f"Error stopping monitoring: {str(e)}")
        
        # Add file interaction monitoring display section
        st.subheader("USB File Interactions")
        
        # Get USB drives
        usb_drives = []
        try:
            usb_drives = get_usb_drive_letters()
        except Exception as e:
            st.warning(f"Error detecting USB drives: {str(e)}")
        
        if usb_drives:
            st.success(f"Detected {len(usb_drives)} USB drive(s): {', '.join(usb_drives)}")
            
            # Create tabs for each detected USB drive
            usb_tabs = st.tabs([f"Drive {drive}" for drive in usb_drives])
            
            for i, drive in enumerate(usb_drives):
                with usb_tabs[i]:
                    st.write(f"Files on USB Drive {drive}")
                    
                    try:
                        files = os.listdir(drive)
                        if files:
                            for file in files:
                                file_path = os.path.join(drive, file)
                                is_dir = os.path.isdir(file_path)
                                icon = "📁" if is_dir else "📄"
                                file_size = ""
                                if not is_dir:
                                    try:
                                        size_bytes = os.path.getsize(file_path)
                                        if size_bytes < 1024:
                                            file_size = f"{size_bytes} bytes"
                                        elif size_bytes < 1024 * 1024:
                                            file_size = f"{size_bytes/1024:.1f} KB"
                                        else:
                                            file_size = f"{size_bytes/(1024*1024):.1f} MB"
                                    except:
                                        file_size = "Unknown size"
                                
                                st.text(f"{icon} {file} {file_size}")
                        else:
                            st.info("No files found on this drive")
                    except Exception as e:
                        st.error(f"Error accessing drive {drive}: {str(e)}")
        else:
            st.info("No USB drives currently connected")
        
        st.info("USB connections and file interactions will generate alerts in the alert management system.")
    
    with tab2:
        st.subheader("Connected USB Devices")
        
        if st.button("Refresh Devices"):
            pass  # This will cause a rerun and refresh the device list
        
        # Get and display USB devices
        try:
            # Use a placeholder to show "Loading..."
            with st.spinner("Scanning for USB devices..."):
                # Redirect stdout to capture the output
                import sys
                from io import StringIO
                
                old_stdout = sys.stdout
                sys.stdout = mystdout = StringIO()
                
                list_connected_usb_devices()
                
                # Restore stdout
                sys.stdout = old_stdout
                
                # Display captured output
                output = mystdout.getvalue()
                if "No USB devices are currently connected" in output:
                    info_message("No USB devices are currently connected.")
                else:
                    # Parse and display the output in a structured way
                    devices = []
                    current_device = {}
                    for line in output.split('\n'):
                        line = line.strip()
                        if line.startswith('=='):
                            if current_device:
                                devices.append(current_device)
                                current_device = {}
                        elif ': ' in line:
                            key, value = line.split(': ', 1)
                            current_device[key] = value
                    
                    if current_device:  # Add the last device
                        devices.append(current_device)
                    
                    # Display devices in cards
                    if devices:
                        st.subheader(f"Found {len(devices)} connected USB devices")
                        
                        # Display in a grid
                        cols = st.columns(2)
                        for i, device in enumerate(devices):
                            with cols[i % 2]:
                                with st.container():
                                    st.markdown("---")
                                    if 'Name' in device:
                                        st.subheader(device['Name'])
                                    else:
                                        st.subheader("Unknown Device")
                                    
                                    for key, value in device.items():
                                        if key != 'Name':  # Name already used as title
                                            st.markdown(f"**{key}:** {value}")
                    else:
                        info_message("No USB devices found or could not parse device information.")
            
            # Available COM Ports
            st.subheader("Available COM Ports")
            
            # Redirect stdout to capture the output
            old_stdout = sys.stdout
            sys.stdout = mystdout = StringIO()
            
            ports = list_available_ports()
            
            # Restore stdout
            sys.stdout = old_stdout
            
            # Display captured output
            output = mystdout.getvalue()
            
            if not ports:
                info_message("No COM ports available")
            else:
                # Display ports
                st.markdown(f"**Found {len(ports)} COM ports**")
                for port in ports:
                    st.markdown(f"- {port}")
                
        except Exception as e:
            error_message(f"Error listing USB devices: {str(e)}")
    
    with tab3:
        st.subheader("USB Alerts")
        
        try:
            alerts = st.session_state.client.get_port_alerts(include_handled=False)
            
            # Create tabs for active and handled alerts
            alert_tabs = st.tabs(["Active Alerts", "Handled Alerts"])
            
            with alert_tabs[0]:
                if not alerts:
                    info_message("No active USB alerts found")
                else:
                    # Convert alerts to DataFrame
                    alert_data = []
                    for i, alert in enumerate(alerts, 1):
                        alert_data.append({
                            "ID": i,
                            "Type": alert.get('type', 'Unknown'),
                            "Severity": alert.get('severity', 'Medium'),
                            "Time": alert.get('timestamp', 'Unknown'),
                            "Message": alert.get('message', 'No message'),
                            "Device": alert.get('device_name', 'Unknown') if 'device_name' in alert else 'N/A'
                        })
                    
                    if alert_data:
                        df = pd.DataFrame(alert_data)
                        st.dataframe(df, use_container_width=True)
                        
                        # Handle alerts section
                        st.subheader("Handle Alert")
                        alert_id = st.number_input("Enter alert ID to handle:", min_value=1, max_value=len(alerts) if alerts else 1, step=1)
                        action = st.radio("Select action:", ["Dismiss", "Send Email Notification"])
                        
                        if st.button("Handle Alert"):
                            action_type = "dismiss" if action == "Dismiss" else "email"
                            if st.session_state.client.handle_port_alert(alert_id - 1, action_type):
                                success_message(f"Alert {action_type}ed successfully")
                                time.sleep(1)
                                st.rerun()
                            else:
                                error_message("Failed to handle alert")
            
            with alert_tabs[1]:
                handled_alerts = st.session_state.client.get_port_alerts(include_handled=True)
                handled_alerts = [a for a in handled_alerts if a.get("handled", False)]
                
                if not handled_alerts:
                    info_message("No handled USB alerts found")
                else:
                    # Convert alerts to DataFrame
                    alert_data = []
                    for i, alert in enumerate(handled_alerts, 1):
                        alert_data.append({
                            "ID": i,
                            "Type": alert.get('type', 'Unknown'),
                            "Severity": alert.get('severity', 'Medium'),
                            "Time": alert.get('timestamp', 'Unknown'),
                            "Message": alert.get('message', 'No message'),
                            "Handled Time": alert.get('handled_time', 'Unknown'),
                            "Action": alert.get('handled_action', 'Unknown')
                        })
                    
                    if alert_data:
                        df = pd.DataFrame(alert_data)
                        st.dataframe(df, use_container_width=True)
            
        except Exception as e:
            error_message(f"Error retrieving alerts: {str(e)}")

def user_activity_page():
    st.subheader("User Activity Monitor")
    
    tab1, tab2 = st.tabs(["Active Users", "User Action History"])
    
    with tab1:
        st.subheader("Active Users")
        
        try:
            active_users = st.session_state.client.get_active_users()
            if not active_users:
                info_message("No active users")
            else:
                # Convert to DataFrame for better display
                user_data = []
                for username, session in active_users.items():
                    user_data.append({
                        "Username": username,
                        "Session Start": session.get('start_time', 'Unknown'),
                        "Status": session.get('status', 'Unknown'),
                        "Session ID": session.get('session_id', 'Unknown'),
                        "IP Address": session.get('ip_address', 'Unknown')
                    })
                
                df = pd.DataFrame(user_data)
                st.dataframe(df, use_container_width=True)
                
                # Show recent actions for each user
                st.subheader("Recent User Actions")
                
                for username in active_users.keys():
                    with st.expander(f"Recent actions for {username}"):
                        actions = st.session_state.client.get_user_actions(username)
                        if actions:
                            # Show last 5 actions
                            recent_actions = actions[-5:]
                            action_data = []
                            for action in recent_actions:
                                action_data.append({
                                    "Timestamp": action['timestamp'],
                                    "Action": action['action'],
                                    "File": action['filepath'],
                                    "Status": action['status']
                                })
                            
                            action_df = pd.DataFrame(action_data)
                            st.dataframe(action_df, use_container_width=True)
                        else:
                            st.info("No actions recorded")
        except Exception as e:
            error_message(f"Error retrieving user data: {str(e)}")
    
    with tab2:
        st.subheader("User Action History")
        
        try:
            active_users = st.session_state.client.get_active_users()
            if not active_users:
                info_message("No users to display")
            else:
                username = st.selectbox("Select user to view detailed action history:", list(active_users.keys()))
                
                if username:
                    actions = st.session_state.client.get_user_actions(username)
                    if not actions:
                        info_message(f"No actions recorded for {username}")
                    else:
                        # Convert to DataFrame for better display
                        action_data = []
                        for action in actions:
                            action_data.append({
                                "Timestamp": action['timestamp'],
                                "Action": action['action'],
                                "File": action['filepath'],
                                "Status": action['status']
                            })
                        
                        df = pd.DataFrame(action_data)
                        st.dataframe(df, use_container_width=True)
                        
                        # Visualization
                        st.subheader("Action Types")
                        action_counts = df['Action'].value_counts()
                        
                        fig, ax = plt.subplots()
                        action_counts.plot(kind='pie', autopct='%1.1f%%', ax=ax)
                        ax.set_ylabel('')
                        st.pyplot(fig)
        except Exception as e:
            error_message(f"Error retrieving user actions: {str(e)}")

def alert_management_page():
    st.subheader("Alert Management")
    
    alert_tabs = st.tabs(["System Alerts", "Port Alerts"])
    
    with alert_tabs[0]:
        st.subheader("System Alerts")
        
        include_handled = st.checkbox("Include handled alerts", key="system_include_handled")
        
        try:
            alerts = st.session_state.client.get_alerts(include_handled=include_handled)
            
            if not alerts:
                info_message("No system alerts found")
            else:
                # Convert to DataFrame for better display
                alert_data = []
                for i, alert in enumerate(alerts, 1):
                    alert_data.append({
                        "ID": i,
                        "Type": alert.get('type', 'Unknown'),
                        "Severity": alert.get('severity', 'Medium'),
                        "User": alert.get('username', 'Unknown'),
                        "Time": alert.get('timestamp', 'Unknown'),
                        "Message": alert.get('message', 'No message'),
                        "Status": "Handled" if alert.get('handled', False) else "Active"
                    })
                
                df = pd.DataFrame(alert_data)
                st.dataframe(df, use_container_width=True)
                
                # Only show handling options for active alerts
                active_alerts = [a for a in alerts if not a.get('handled', False)]
                if active_alerts:
                    st.subheader("Handle Alert")
                    alert_id = st.number_input("Enter alert ID to handle:", min_value=1, max_value=len(active_alerts), step=1, key="system_alert_id")
                    action = st.radio("Select action:", ["Dismiss", "Send Email Notification"], key="system_alert_action")
                    
                    if st.button("Handle Alert", key="handle_system_alert"):
                        action_type = "dismiss" if action == "Dismiss" else "email"
                        if alert_id <= len(active_alerts):
                            if st.session_state.client.handle_alert(alert_id - 1, action_type):
                                success_message(f"Alert {action_type}ed successfully")
                                time.sleep(1)
                                st.rerun()
                            else:
                                error_message("Failed to handle alert")
                        else:
                            error_message("Invalid alert ID")
        except Exception as e:
            error_message(f"Error retrieving system alerts: {str(e)}")
    
    with alert_tabs[1]:
        st.subheader("Port Alerts")
        
        include_handled = st.checkbox("Include handled alerts", key="port_include_handled")
        
        try:
            alerts = st.session_state.client.get_port_alerts(include_handled=include_handled)
            
            if not alerts:
                info_message("No port alerts found")
            else:
                # Convert to DataFrame for better display
                alert_data = []
                for i, alert in enumerate(alerts, 1):
                    alert_data.append({
                        "ID": i,
                        "Type": alert.get('type', 'Unknown'),
                        "Severity": alert.get('severity', 'Medium'),
                        "Time": alert.get('timestamp', 'Unknown'),
                        "Message": alert.get('message', 'No message'),
                        "Status": "Handled" if alert.get('handled', False) else "Active"
                    })
                
                df = pd.DataFrame(alert_data)
                st.dataframe(df, use_container_width=True)
                
                # Only show handling options for active alerts
                active_alerts = [a for a in alerts if not a.get('handled', False)]
                if active_alerts:
                    st.subheader("Handle Alert")
                    alert_id = st.number_input("Enter alert ID to handle:", min_value=1, max_value=len(active_alerts), step=1, key="port_alert_id")
                    action = st.radio("Select action:", ["Dismiss", "Send Email Notification"], key="port_alert_action")
                    
                    if st.button("Handle Alert", key="handle_port_alert"):
                        action_type = "dismiss" if action == "Dismiss" else "email"
                        if alert_id <= len(active_alerts):
                            if st.session_state.client.handle_port_alert(alert_id - 1, action_type):
                                success_message(f"Alert {action_type}ed successfully")
                                time.sleep(1)
                                st.rerun()
                            else:
                                error_message("Failed to handle alert")
                        else:
                            error_message("Invalid alert ID")
        except Exception as e:
            error_message(f"Error retrieving port alerts: {str(e)}")

def user_dashboard():
    st.title(f"User Dashboard: {st.session_state.username}")
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["View Files", "Request File Access", "Decrypt File"])
    
    # Logout button
    if st.sidebar.button("Logout"):
        logout()
    
    # Page content
    if page == "View Files":
        view_files_page()
    
    elif page == "Request File Access":
        st.subheader("Request File Access")
        
        try:
            files = st.session_state.client.list_files()
            if not files:
                info_message("No files available to request.")
                return
            
            selected_file = st.selectbox("Select file to request access:", files)
            
            if st.button("Request Access"):
                with st.spinner("Sending request to admin..."):
                    key = st.session_state.client.request_file_access(selected_file)
                    
                    if key:
                        success_message("Access granted!")
                        st.code(key, language="text")
                        st.info("Keep this key safe. You'll need it to decrypt the file.")
                    else:
                        error_message("Access request failed or denied.")
        except Exception as e:
            error_message(f"Error: {str(e)}")
    
    elif page == "Decrypt File":
        st.subheader("Decrypt File")
        
        try:
            files = st.session_state.client.list_files()
            if not files:
                info_message("No files available to decrypt.")
                return
            
            # Format files as options with encryption status
            file_options = []
            for file in files:
                encrypted = check_file_encryption_status(file)
                status = " [ENCRYPTED]" if encrypted else ""
                file_options.append(f"{file}{status}")
                
            selected_file = st.selectbox("Select file to decrypt:", file_options)
            
            # Extract filename without status
            filename = selected_file.split(" [ENCRYPTED]")[0]
            
            decryption_key = st.text_input("Enter decryption key:", type="password")
            
            if st.button("Decrypt File"):
                if "[ENCRYPTED]" not in selected_file:
                    warning_message("This file is not encrypted.")
                else:
                    full_path = os.path.join("confidential", filename)
                    if st.session_state.client.decrypt_file(full_path, decryption_key):
                        success_message("File decrypted successfully!")
                    else:
                        error_message("Failed to decrypt file. Invalid key or corrupted file.")
        except Exception as e:
            error_message(f"Error: {str(e)}")

def admin_dashboard():
    st.title(f"Admin Dashboard: {st.session_state.username}")
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to", 
        ["File Encryption Management", "File Monitoring", "User Activity", 
         "External Device Monitoring", "Alert Management"]
    )
    
    # Logout button
    if st.sidebar.button("Logout"):
        logout()
    
    # Page content
    if page == "File Encryption Management":
        file_encryption_page()
    
    elif page == "File Monitoring":
        file_monitoring_page()
    
    elif page == "User Activity":
        user_activity_page()
    
    elif page == "External Device Monitoring":
        usb_monitoring_page()
    
    elif page == "Alert Management":
        alert_management_page()

def main():
    # Check server periodically
    if st.session_state.logged_in:
        if not is_server_running():
            st.error("Lost connection to the DLP server. Please ensure the server is running and refresh the page.")
            # Force logout if server is down
            if st.session_state.client:
                try:
                    st.session_state.client.close()
                except:
                    pass
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.client = None
            st.session_state.user_type = None
            st.session_state.monitoring_active = False
            if st.session_state.monitor and getattr(st.session_state.monitor, 'running', False):
                st.session_state.monitor.stop_monitoring()
            st.session_state.monitor = None
            st.rerun()
    
    if not st.session_state.logged_in:
        login_page()
    else:
        if st.session_state.user_type == "admin":
            admin_dashboard()
        else:
            user_dashboard()

if __name__ == "__main__":
    main()


