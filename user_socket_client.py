import socket
import json
import os
import time
import select


class UserClient:
    def __init__(self, host="localhost", port=5000):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            self.users = {"user1": "pass1", "user2": "pass2"}
            self.session_type = None
            self.username = None
            self.connected = True
        except ConnectionRefusedError:
            print(
                f"Error: Could not connect to server. Make sure the server is running."
            )
            self.connected = False
            raise

    def is_socket_valid(self):
        """Check if the socket is valid and connected"""
        if not self.connected:
            return False
            
        try:
            # Try a non-blocking probe
            self.socket.getpeername()
            return True
        except:
            self.connected = False
            return False

    def reconnect(self, host="localhost", port=5000):
        """Attempt to reconnect to the server"""
        try:
            # Close old socket if it exists
            try:
                self.socket.close()
            except:
                pass
                
            # Create new socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            self.connected = True
            return True
        except Exception:
            self.connected = False
            return False

    def send_request(self, request):
        try:
            if not self.is_socket_valid():
                raise ConnectionError("Socket is not valid")
                
            self.socket.send(json.dumps(request).encode())
        except Exception as e:
            self.connected = False
            print(f"Error sending request: {str(e)}")
            raise

    def receive_response(self):
        try:
            if not self.is_socket_valid():
                raise ConnectionError("Socket is not valid")
                
            ready = select.select([self.socket], [], [], 30)  # 30 seconds timeout
            if ready[0]:
                # Read size header first
                size_header = self.socket.recv(10).decode()
                if not size_header:
                    self.connected = False
                    raise ConnectionError("Server closed connection")

                # Get expected response size
                expected_size = int(size_header.strip())

                # Read full response
                chunks = []
                bytes_received = 0
                while bytes_received < expected_size:
                    chunk = self.socket.recv(min(1024, expected_size - bytes_received))
                    if not chunk:
                        self.connected = False
                        raise ConnectionError("Connection closed while receiving data")
                    chunks.append(chunk)
                    bytes_received += len(chunk)

                data = b"".join(chunks).decode()
                return json.loads(data)
            raise TimeoutError("Server response timeout")
        except Exception as e:
            self.connected = False
            print(f"Error receiving response: {str(e)}")
            raise

    def admin_login(self, username, password):
        request = {
            "type": "auth",
            "username": username,
            "password": password,
            "auth_type": "admin",
        }
        self.send_request(request)
        response = self.receive_response()

        if response["status"] == "success":
            self.session_type = "admin"
            self.username = username
        return response

    def user_login(self, username, password):
        request = {
            "type": "auth",
            "username": username,
            "password": password,
            "auth_type": "user",
        }
        self.send_request(request)
        response = self.receive_response()

        if response["status"] == "success":
            self.session_type = "user"
            self.username = username
            return True
        elif response["status"] == "blocked":
            # Special handling for blocked users
            print("\n⛔ " + response["message"])
            return "blocked"
        return False

    def list_files(self, include_encryption_status=False):
        files = []
        if os.path.exists("confidential"):
            for file in os.listdir("confidential"):
                if os.path.isfile(os.path.join("confidential", file)):
                    files.append(file)
        
        if include_encryption_status:
            # Include encryption status if requested
            result = []
            for file in files:
                encrypted = False
                try:
                    if os.path.exists("encryption_keys.json"):
                        with open("encryption_keys.json", "r") as f:
                            keys = json.load(f)
                        encrypted = file in keys
                except Exception:
                    pass
                result.append({"name": file, "encrypted": encrypted})
            return result
        
        return files

    def check_for_notifications(self, timeout=0.1):
        try:
            ready = select.select([self.socket], [], [], timeout)
            if ready[0]:
                # Read size header first
                size_header = self.socket.recv(10).decode()
                if not size_header:
                    return None

                # Get expected response size
                try:
                    expected_size = int(size_header.strip())
                except ValueError:
                    return None

                # Read full response
                chunks = []
                bytes_received = 0
                while bytes_received < expected_size:
                    chunk = self.socket.recv(min(1024, expected_size - bytes_received))
                    if not chunk:
                        return None
                    chunks.append(chunk)
                    bytes_received += len(chunk)

                data = b"".join(chunks).decode()
                response = json.loads(data)

                if (
                    response.get("type") == "notification"
                    and response.get("message") == "access_approved"
                ):
                    return response.get("key")
            return None
        except Exception as e:
            print(f"Error checking notifications: {str(e)}")
            return None

    def request_file_access(self, filename):
        print("Sending request to server...")
        try:
            request = {
                "type": "request_access",
                "username": self.username,
                "filename": filename,
            }
            self.send_request(request)
            response = self.receive_response()

            if response["status"] == "pending":
                print("\nRequest sent to admin. Waiting for approval...")
                for i in range(30):  # 30 second timeout
                    print(f"\rWaiting for approval... {i+1}/30s", end="", flush=True)
                    time.sleep(1)

                    # Check for notifications first
                    key = self.check_for_notifications()
                    if key:
                        print("\nRequest approved!")
                        return key

                    # If no notification, check explicitly
                    check_request = {
                        "type": "check_approval",
                        "username": self.username,
                        "filename": filename,
                    }
                    try:
                        self.send_request(check_request)
                        check_response = self.receive_response()
                        if check_response.get("status") == "approved":
                            print("\nRequest approved!")
                            return check_response.get("key")
                    except TimeoutError:
                        continue
                print("\nRequest timed out. Please try again later.")
            return None
        except KeyboardInterrupt:
            print("\nCancelled waiting for approval.")
            return None
        except Exception as e:
            print(f"\nError requesting file access: {str(e)}")
            return None

    def decrypt_file(self, filename, key):
        from encryption import EncryptionManager

        em = EncryptionManager()
        return em.decrypt_file(filename, key)

    def encrypt_file(self, filename):
        if self.session_type != "admin":
            return None

        request = {"type": "encrypt", "filename": filename}
        self.send_request(request)
        response = self.receive_response()
        return response.get("key")

    def get_keys(self):
        if self.session_type != "admin":
            return None

        request = {"type": "get_keys"}
        self.send_request(request)
        response = self.receive_response()
        if response.get("status") == "success":
            return response.get("keys", {})
        return {}

    def get_pending_requests(self):
        if self.session_type != "admin":
            return []

        request = {"type": "get_pending_requests"}
        self.send_request(request)
        response = self.receive_response()
        return response.get("requests", [])

    def approve_request(self, username, filename):
        if self.session_type != "admin":
            print("Error: Admin privileges required")
            return False

        if not username or not filename:
            print("Error: Invalid username or filename")
            return False

        request = {
            "type": "approve_request",
            "username": username,
            "filename": filename,
        }

        try:
            self.send_request(request)
            response = self.receive_response()

            if response.get("status") == "success":
                return True
            else:
                error_msg = response.get("message", "Unknown error")
                print(f"Error: {error_msg}")
                return False

        except Exception as e:
            print(f"Error approving request: {str(e)}")
            return False

    def get_active_users(self):
        if self.session_type != "admin":
            return None

        request = {"type": "get_active_users"}
        self.send_request(request)
        response = self.receive_response()
        return response.get("users", {})

    def get_user_actions(self, username):
        if self.session_type != "admin":
            return None

        request = {"type": "get_user_actions", "username": username}
        self.send_request(request)
        response = self.receive_response()
        return response.get("actions", [])

    def get_alerts(self, include_handled=False):
        if self.session_type != "admin":
            return None

        request = {"type": "get_alerts", "include_handled": include_handled}
        self.send_request(request)
        response = self.receive_response()
        return response.get("alerts", [])

    def handle_alert(self, alert_index, action="dismiss"):
        if self.session_type != "admin":
            return False

        request = {"type": "handle_alert", "alert_index": alert_index, "action": action}
        self.send_request(request)
        response = self.receive_response()
        return response.get("status") == "success"

    def get_file_transfers(self):
        if self.session_type != "admin":
            return None

        request = {"type": "get_file_transfers"}
        self.send_request(request)
        response = self.receive_response()
        return response.get("transfers", [])

    def check_file_modifications(self, filename):

        request = {"type": "check_file_modifications", "filename": filename}
        self.send_request(request)
        response = self.receive_response()
        return response.get("modifications")

    def get_file_modifications(self, filename):
        if self.session_type != "admin":
            return None

        request = {"type": "get_file_modifications", "filename": filename}
        self.send_request(request)
        response = self.receive_response()
        return response.get("modifications", [])

    def get_monitored_folders(self):
        if self.session_type != "admin":
            return None
        request = {"type": "get_monitored_folders"}
        self.send_request(request)
        response = self.receive_response()
        return response.get("folders", [])

    def add_monitored_folder(self, folder_path):
        if self.session_type != "admin":
            return False

        request = {"type": "add_monitored_folder", "folder_path": folder_path}
        self.send_request(request)
        response = self.receive_response()
        return response.get("status") == "success"

    def get_port_alerts(self, include_handled=False):
        if self.session_type != "admin":
            return None

        request = {"type": "get_port_alerts", "include_handled": include_handled}
        self.send_request(request)
        response = self.receive_response()
        return response.get("alerts", [])

    def handle_port_alert(self, alert_index, action="dismiss"):
        if self.session_type != "admin":
            return False

        request = {
            "type": "handle_port_alert",
            "alert_index": alert_index,
            "action": action,
        }
        self.send_request(request)
        response = self.receive_response()
        return response.get("status") == "success"

    def get_all_users(self):
        """Get a list of all users with their status"""
        if self.session_type != "admin":
            return None
            
        request = {"type": "get_users"}
        self.send_request(request)
        response = self.receive_response()
        
        if response.get("status") == "success":
            return response.get("users", [])
        return []
    
    def block_user(self, username):
        """Block a user from accessing the system"""
        if self.session_type != "admin":
            return False
            
        request = {"type": "block_user", "username": username}
        self.send_request(request)
        response = self.receive_response()
        
        return response.get("status") == "success"
    
    def unblock_user(self, username):
        """Unblock a user"""
        if self.session_type != "admin":
            return False
            
        request = {"type": "unblock_user", "username": username}
        self.send_request(request)
        response = self.receive_response()
        
        return response.get("status") == "success"

    def close(self):
        try:
            self.socket.close()
        except Exception:
            pass
        self.connected = False
