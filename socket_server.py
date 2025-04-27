import socket
import json
import threading
from encryption import EncryptionManager
import logging
from queue import Queue
import os
import sys
from io import StringIO


class SocketServer:
    def __init__(self, host="localhost", port=5000):
        # Setup basic logging
        self.logger = logging.getLogger("dlp_server")
        handler = logging.FileHandler("logs/server.log")
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        self.host = host
        self.port = port
        self.server = None  # Initialize to None, will create socket when starting
        self.is_running = False  # Flag to control server running state
        self.is_shutting_down = False  # Flag to prevent duplicate shutdown messages
        self.encryption_manager = EncryptionManager()
        self.pending_requests = Queue()
        self.approved_requests = {}
        self.clients = {}
        self.active_sessions = {}
        self.admins = {"admin1": "pass1", "admin2": "pass2"}
        self.users = {"user1": "pass1", "user2": "pass2"}
        self.user_connections = {}  # Track user connections by username
        self.blocked_users = set()  # Track blocked users
        
        # Load blocked users from file if it exists
        self.load_blocked_users()

        # Initialize file monitor first
        from file_monitor import FileMonitor

        self.file_monitor = FileMonitor()
        self.file_monitor.start()
        self.logger.info("File monitoring system initialized")

        self.logger.info("Server initialized")
    
    def create_server_socket(self):
        """Create a new server socket"""
        try:
            # Close existing socket if there is one
            if self.server:
                try:
                    self.server.close()
                except Exception:
                    pass
                
            # Create new socket
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.logger.info("Created new server socket")
            return True
        except Exception as e:
            self.logger.error(f"Error creating server socket: {str(e)}")
            return False
    
    def load_blocked_users(self):
        """Load blocked users from a file"""
        try:
            if os.path.exists("blocked_users.json"):
                with open("blocked_users.json", "r") as f:
                    data = json.load(f)
                    self.blocked_users = set(data.get("blocked_users", []))
                self.logger.info(f"Loaded {len(self.blocked_users)} blocked users")
            else:
                self.blocked_users = set()
        except Exception as e:
            self.logger.error(f"Error loading blocked users: {str(e)}")
            self.blocked_users = set()
    
    def save_blocked_users(self):
        """Save blocked users to a file"""
        try:
            with open("blocked_users.json", "w") as f:
                json.dump({"blocked_users": list(self.blocked_users)}, f)
            self.logger.info(f"Saved {len(self.blocked_users)} blocked users")
            return True
        except Exception as e:
            self.logger.error(f"Error saving blocked users: {str(e)}")
            return False
    
    def block_user(self, username):
        """Block a user from accessing the system"""
        if username in self.users:
            self.blocked_users.add(username)
            self.save_blocked_users()
            
            # Disconnect the user if currently connected
            if username in self.user_connections:
                try:
                    user_client = self.user_connections[username]
                    notification = {
                        "type": "notification",
                        "message": "account_blocked",
                    }
                    self.notify_user(user_client, notification)
                    # The client connection will be closed in the handle_client method
                except Exception as e:
                    self.logger.error(f"Error notifying blocked user: {str(e)}")
            
            self.logger.info(f"User {username} has been blocked")
            return True
        return False
    
    def unblock_user(self, username):
        """Unblock a user"""
        if username in self.blocked_users:
            self.blocked_users.remove(username)
            self.save_blocked_users()
            self.logger.info(f"User {username} has been unblocked")
            return True
        return False
    
    def is_user_blocked(self, username):
        """Check if a user is blocked"""
        return username in self.blocked_users

    def start(self):
        try:
            # Create a new socket when starting
            if not self.create_server_socket():
                self.logger.error("Failed to create server socket, cannot start server")
                return
                
            self.server.bind((self.host, self.port))
            self.server.listen(5)
            self.is_running = True
            self.logger.info(f"DLP Server started on {self.host}:{self.port}")
            print(f"DLP Server is listening on {self.host}:{self.port}")
            print("Waiting for connections...")
            
            while self.is_running:
                try:
                    # Add timeout to socket accept to allow for clean shutdown
                    self.server.settimeout(1.0)
                    client, address = self.server.accept()
                    self.logger.info(f"New connection from {address[0]}:{address[1]}")
                    print(f"New client connected from {address[0]}:{address[1]}")
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client,),
                    )
                    client_thread.start()
                except socket.timeout:
                    # This is expected due to the timeout, just continue the loop
                    continue
                except OSError as e:
                    if self.is_running:  # Only log if we're still supposed to be running
                        self.logger.error(f"Error accepting connection: {str(e)}")
                        # Try to recreate the socket
                        if "10038" in str(e):  # Socket operation on non-socket
                            if self.create_server_socket():
                                self.server.bind((self.host, self.port))
                                self.server.listen(5)
                                self.logger.info("Server socket recreated after error")
                except Exception as e:
                    if self.is_running:  # Only log if we're still supposed to be running
                        self.logger.error(f"Error accepting connection: {str(e)}")
        except Exception as e:
            self.logger.error(f"Server error: {str(e)}", exc_info=True)
            print(f"Server error: {str(e)}")
        finally:
            self.stop()

    def send_response(self, client, response):
        try:
            # Convert response to JSON and send with size prefix
            response_json = json.dumps(response)
            response_bytes = response_json.encode()
            size = len(response_bytes)
            size_header = f"{size:10}".encode()
            client.send(size_header)
            client.send(response_bytes)
        except Exception as e:
            self.logger.error(f"Error sending response: {str(e)}")
            raise

    def notify_user(self, client, notification):
        try:
            response_json = json.dumps(notification)
            response_bytes = response_json.encode()
            size = len(response_bytes)
            size_header = f"{size:10}".encode()
            client.send(size_header)
            client.send(response_bytes)
        except Exception as e:
            self.logger.error(f"Error sending notification: {str(e)}")
            raise

    def handle_client(self, client):
        try:
            while self.is_running:
                try:
                    # Add timeout to client socket to allow checking is_running
                    client.settimeout(1.0)
                    data = client.recv(1024).decode()
                    if not data:
                        break

                    request = json.loads(data)
                    if client in self.active_sessions:
                        username = self.active_sessions[client]["username"]
                        self.file_monitor.log_action(
                            username,
                            request.get("type", "unknown"),
                            request.get("filename", "n/a"),
                        )
                    response = self.process_request(request, client)
                    self.send_response(client, response)
                except socket.timeout:
                    # This is expected due to the timeout, just continue if we're still running
                    if not self.is_running:
                        break
                    continue
                except ConnectionError as e:
                    self.logger.error(f"Connection error with client: {str(e)}")
                    break
                except Exception as e:
                    self.logger.error(f"Error handling client: {str(e)}")
                    break
        except Exception as e:
            self.logger.error(f"Error handling client: {str(e)}")
        finally:
            if client in self.active_sessions:
                username = self.active_sessions[client].get("username")
                self.file_monitor.end_session(username)
                if username in self.user_connections:
                    del self.user_connections[username]
                del self.active_sessions[client]
            if client in self.clients:
                del self.clients[client]
            try:
                client.close()
            except Exception:
                pass

    def process_request(self, request, client):
        try:
            req_type = request.get("type")

            # Add username to file monitor for tracking actions
            if client in self.active_sessions:
                username = self.active_sessions[client]["username"]
                self.file_monitor.set_current_user(username)

            if req_type == "auth":
                username = request.get("username")
                password = request.get("password")
                auth_type = request.get("auth_type")

                if auth_type == "admin":
                    if username in self.admins and self.admins[username] == password:
                        self.active_sessions[client] = {
                            "type": "admin",
                            "username": username,
                        }
                        self.file_monitor.register_session(username, client)
                        return {
                            "status": "success",
                            "message": "Admin authentication successful",
                        }
                else:
                    # Check if user is blocked before authenticating
                    if username in self.blocked_users:
                        self.logger.warning(f"Blocked user {username} attempted to login")
                        return {
                            "status": "blocked",
                            "message": "Your account has been blocked. Please contact an administrator."
                        }
                    
                    if username in self.users and self.users[username] == password:
                        self.active_sessions[client] = {
                            "type": "user",
                            "username": username,
                        }
                        self.user_connections[username] = (
                            client  # Track user connection
                        )
                        self.file_monitor.register_session(username, client)
                        return {
                            "status": "success",
                            "message": "User authentication successful",
                        }

                return {"status": "failed", "message": "Invalid credentials"}
                
            elif req_type == "block_user":
                if self.active_sessions.get(client, {}).get("type") == "admin":
                    username = request.get("username")
                    if self.block_user(username):
                        return {"status": "success", "message": f"User {username} blocked successfully"}
                    return {"status": "failed", "message": "Failed to block user"}
                return {"status": "failed", "message": "Unauthorized"}
                
            elif req_type == "unblock_user":
                if self.active_sessions.get(client, {}).get("type") == "admin":
                    username = request.get("username")
                    if self.unblock_user(username):
                        return {"status": "success", "message": f"User {username} unblocked successfully"}
                    return {"status": "failed", "message": "Failed to unblock user"}
                return {"status": "failed", "message": "Unauthorized"}
                
            elif req_type == "get_users":
                if self.active_sessions.get(client, {}).get("type") == "admin":
                    user_list = []
                    for username in self.users.keys():
                        user_list.append({
                            "username": username,
                            "blocked": username in self.blocked_users,
                            "active": username in self.user_connections
                        })
                    return {"status": "success", "users": user_list}
                return {"status": "failed", "message": "Unauthorized"}

            elif req_type == "register":
                self.clients[client] = request.get("client_type")
                return {"status": "success"}

            elif req_type == "request_access":
                self.pending_requests.put(
                    {
                        "username": request.get("username"),
                        "filename": request.get("filename"),
                        "client": client,
                    }
                )
                return {"status": "pending"}

            elif req_type == "approve_request":
                if self.active_sessions.get(client, {}).get("type") == "admin":
                    username = request.get("username")
                    filename = request.get("filename")

                    # Validate request exists
                    found_request = False
                    temp_queue = Queue()

                    try:
                        while not self.pending_requests.empty():
                            req = self.pending_requests.get()
                            if (
                                req["username"] == username
                                and req["filename"] == filename
                            ):
                                found_request = True
                            else:
                                temp_queue.put(req)
                    finally:
                        while not temp_queue.empty():
                            self.pending_requests.put(temp_queue.get())

                    if not found_request:
                        return {"status": "failed", "message": "Request not found"}

                    # Get encryption key using the full file path
                    full_path = os.path.join("confidential", filename)
                    if not os.path.exists(full_path):
                        return {
                            "status": "failed",
                            "message": f"File {filename} not found",
                        }

                    # First check if file is already encrypted
                    keys = self.encryption_manager.get_all_keys()
                    if filename not in keys:
                        # Encrypt the file if it's not already encrypted
                        key = self.encryption_manager.encrypt_file(full_path)
                        if not key:
                            return {
                                "status": "failed",
                                "message": "Failed to encrypt file",
                            }
                    else:
                        key = keys[filename].get("key")
                        if not key:
                            return {
                                "status": "failed",
                                "message": "Invalid encryption key",
                            }

                    # Store approval
                    self.approved_requests[f"{username}:{filename}"] = key
                    self.logger.info(f"Access approved for {username} to {filename}")

                    # Notify user if connected
                    user_client = self.user_connections.get(username)
                    if user_client:
                        try:
                            notification = {
                                "type": "notification",
                                "message": "access_approved",
                                "key": key,
                            }
                            self.notify_user(user_client, notification)
                        except Exception as e:
                            self.logger.error(
                                f"Failed to notify user {username}: {str(e)}"
                            )

                    return {"status": "success", "key": key}
                return {"status": "failed", "message": "Unauthorized"}

            elif req_type == "check_approval":
                username = request.get("username")
                filename = request.get("filename")
                key = self.approved_requests.get(f"{username}:{filename}")
                if key:
                    # Remove from approved requests once retrieved
                    del self.approved_requests[f"{username}:{filename}"]
                    self.logger.info(
                        f"Access key retrieved by {username} for {filename}"
                    )
                    return {"status": "approved", "key": key}
                return {"status": "pending"}

            elif req_type == "get_pending_requests":
                if self.active_sessions.get(client, {}).get("type") == "admin":
                    # Convert queue to list without removing items
                    pending = []
                    temp_queue = Queue()

                    try:
                        while not self.pending_requests.empty():
                            req = self.pending_requests.get()
                            if all(k in req for k in ["username", "filename"]):
                                pending.append(
                                    {
                                        "username": req["username"],
                                        "filename": req["filename"],
                                    }
                                )
                            temp_queue.put(req)
                    finally:
                        # Ensure requests are restored even if there's an error
                        while not temp_queue.empty():
                            self.pending_requests.put(temp_queue.get())

                    self.logger.info(
                        f"Admin {self.active_sessions[client]['username']} viewed {len(pending)} pending requests"
                    )
                    return {"status": "success", "requests": pending}
                return {"status": "failed", "message": "Unauthorized"}

            elif req_type == "get_keys":
                if self.active_sessions.get(client, {}).get("type") == "admin":
                    keys = self.encryption_manager.get_all_keys()
                    self.logger.info(
                        f"Keys viewed by {self.active_sessions[client]['username']}"
                    )
                    return {"status": "success", "keys": keys}
                return {"status": "failed", "message": "Unauthorized"}

            elif req_type == "encrypt":
                if self.active_sessions.get(client, {}).get("type") == "admin":
                    filename = request.get("filename")
                    key = self.encryption_manager.encrypt_file(filename)
                    return {"status": "success", "key": key}
                return {"status": "failed", "message": "Unauthorized"}

            elif req_type == "get_active_users":
                if self.active_sessions.get(client, {}).get("type") == "admin":
                    try:
                        active_users = self.file_monitor.get_active_sessions()
                        self.logger.info(
                            f"Active users requested by admin: {active_users}"
                        )
                        return {"status": "success", "users": active_users}
                    except Exception as e:
                        self.logger.error(
                            f"Error getting active users: {str(e)}", exc_info=True
                        )
                        return {
                            "status": "failed",
                            "message": "Error retrieving active users",
                        }
                return {"status": "failed", "message": "Unauthorized"}

            elif req_type == "get_user_actions":
                if self.active_sessions.get(client, {}).get("type") == "admin":
                    username = request.get("username")
                    actions = self.file_monitor.get_user_actions(
                        username, limit=50
                    )  # Limit results
                    return {"status": "success", "actions": actions}
                return {"status": "failed", "message": "Unauthorized"}

            elif req_type == "get_alerts":
                if self.active_sessions.get(client, {}).get("type") == "admin":
                    include_handled = request.get("include_handled", False)
                    alerts = self.file_monitor.get_alerts(
                        include_handled=include_handled
                    )
                    return {"status": "success", "alerts": alerts}
                return {"status": "failed", "message": "Unauthorized"}

            elif req_type == "handle_alert":
                if self.active_sessions.get(client, {}).get("type") == "admin":
                    alert_index = request.get("alert_index")
                    action = request.get("action", "dismiss")

                    if self.file_monitor.mark_alert_handled(alert_index):
                        if action == "email":
                            # Send email notification
                            alert = self.file_monitor.alerts[alert_index]
                            self.send_alert_email(alert)
                        return {"status": "success"}
                    return {"status": "failed", "message": "Invalid alert index"}
                return {"status": "failed", "message": "Unauthorized"}

            elif req_type == "get_file_transfers":
                if self.active_sessions.get(client, {}).get("type") == "admin":
                    transfers = self.file_monitor.get_file_transfers()
                    return {"status": "success", "transfers": transfers}
                return {"status": "failed", "message": "Unauthorized"}

            elif req_type == "check_file_modifications":
                if self.active_sessions.get(client, {}).get("type") == "admin":
                    filename = request.get("filename")
                    modifications = self.file_monitor.check_modifications(filename)
                    return {"status": "success", "modifications": modifications}
                return {"status": "failed", "message": "Unauthorized"}

            elif req_type == "get_file_modifications":
                if self.active_sessions.get(client, {}).get("type") == "admin":
                    filename = request.get("filename")
                    modifications = self.file_monitor.get_modifications(filename)
                    return {"status": "success", "modifications": modifications}
                return {"status": "failed", "message": "Unauthorized"}

            elif req_type == "get_monitored_folders":
                if self.active_sessions.get(client, {}).get("type") == "admin":
                    folders = self.file_monitor.get_monitored_folders()
                    return {"status": "success", "folders": folders}
                return {"status": "failed", "message": "Unauthorized"}

            elif req_type == "add_monitored_folder":
                if self.active_sessions.get(client, {}).get("type") == "admin":
                    folder_path = request.get("folder_path")
                    success = self.file_monitor.add_monitored_folder(folder_path)
                    if success:
                        self.logger.info(f"Added folder to monitoring: {folder_path}")
                        return {"status": "success"}
                    return {"status": "failed", "message": "Invalid folder path"}
                return {"status": "failed", "message": "Unauthorized"}

            elif req_type == "get_port_alerts":
                if self.active_sessions.get(client, {}).get("type") == "admin":
                    include_handled = request.get("include_handled", False)
                    # Use port monitor to get alerts
                    from port_monitor import PortMonitor

                    port_monitor = PortMonitor()
                    alerts = port_monitor.get_alerts(include_handled)
                    return {"status": "success", "alerts": alerts}
                return {"status": "failed", "message": "Unauthorized"}

            elif req_type == "handle_port_alert":
                if self.active_sessions.get(client, {}).get("type") == "admin":
                    alert_index = request.get("alert_index")
                    action = request.get("action", "dismiss")
                    # Use port monitor to handle alerts
                    from port_monitor import PortMonitor

                    port_monitor = PortMonitor()
                    if port_monitor.mark_alert_handled(alert_index, action):
                        return {"status": "success"}
                    return {"status": "failed", "message": "Invalid alert index"}
                return {"status": "failed", "message": "Unauthorized"}

            # Add more request handling as needed
            return {"status": "unknown_request"}

        except Exception as e:
            self.logger.error(f"Error processing request: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def send_alert_email(self, alert):
        try:
            import requests

            # Mailgun configuration
            MAILGUN_API_KEY = "320690068d6b18741d8abd1af4d85a0c-ac3d5f74-f06a6839"
            MAILGUN_DOMAIN = "sandboxa3628d82a4714395ba7eeea5179f413c.mailgun.org"
            TO_EMAIL = "atharvkulkarni2002@gmail.com"  # Change this to your email
            FROM_EMAIL = f"dlp-alerts@{MAILGUN_DOMAIN}"

            # Prepare email content
            email_subject = f"DLP Alert: {alert['type']} ({alert['severity']})"
            email_body = f"""
Security Alert from DLP System

Type: {alert['type']}
Severity: {alert['severity']}
User: {alert['username']}
File: {alert['filepath']}
Time: {alert['timestamp']}

Message: {alert['message']}

This is an automated message from your DLP system.
            """

            # Send email using Mailgun API
            response = requests.post(
                f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
                auth=("api", MAILGUN_API_KEY),
                data={
                    "from": FROM_EMAIL,
                    "to": TO_EMAIL,
                    "subject": email_subject,
                    "text": email_body,
                },
            )

            if response.status_code == 200:
                self.logger.info(f"Alert email sent successfully for {alert['type']}")
                print("✅ Email alert sent successfully!")
                return True
            else:
                raise Exception(f"Mailgun API error: {response.text}")

        except Exception as e:
            self.logger.error(f"Failed to send alert email: {str(e)}")
            print(f"❌ Failed to send email alert: {str(e)}")
            return False

    def stop(self):
        """Gracefully shut down the server"""
        # Only proceed if we're not already shutting down
        if self.is_shutting_down:
            return
            
        self.is_shutting_down = True
        self.logger.info("Shutting down server...")
        print("Shutting down DLP Server...")
        self.is_running = False  # Set flag to stop all threads
        
        # Close the server socket
        if self.server:
            try:
                self.server.close()
            except Exception as e:
                self.logger.error(f"Error closing server socket: {str(e)}")
        
        # Stop file monitor
        self.file_monitor.stop()
        
        self.logger.info("Server shutdown complete")
        print("Server shutdown complete")


if __name__ == "__main__":
    import signal
    import time

    server = SocketServer()
    shutdown_in_progress = False
    
    # Set up signal handling for graceful shutdown
    def signal_handler(sig, frame):
        global shutdown_in_progress
        if shutdown_in_progress:
            return
            
        shutdown_in_progress = True
        print("\nReceived shutdown signal. Stopping server...")
        server.stop()
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
    
    # Start server in a separate thread
    server_thread = threading.Thread(target=server.start)
    server_thread.daemon = True  # Allow the program to exit even if the thread is running
    server_thread.start()
    
    # Keep the main thread alive to handle signals
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        if not shutdown_in_progress:
            shutdown_in_progress = True
            print("\nStopping server...")
            server.stop()
            sys.exit(0)
