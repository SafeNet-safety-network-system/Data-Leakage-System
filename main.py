from datetime import datetime
from user_socket_client import UserClient
import os
import logging
import time
import threading
from utils import setup_logging, check_file_encryption_status
from port_monitor import PortMonitor, list_connected_usb_devices, list_available_ports

logger = setup_logging(
    "dlp_client"
)


def external_device_monitoring_menu(client):
    monitor = None

    try:
        while True:
            print("\n=== External Device Monitoring ===")
            print("1. Start USB Port Monitoring")
            print("2. Stop USB Port Monitoring")
            print("3. View Connected USB Devices")
            print("4. View Available COM Ports")
            print("5. View USB Alerts")
            print("6. Back")

            try:
                choice = input("\nEnter choice: ")
            except KeyboardInterrupt:
                print("\n\nMonitoring interrupted. Cleaning up...")
                if monitor and hasattr(monitor, "running") and monitor.running:
                    monitor.stop_monitoring()
                print("Returning to previous menu...")
                return

            if choice == "1":
                if not monitor or not hasattr(monitor, "running") or not monitor.running:
                    print("\n🚀 Starting USB port monitoring...")
                    print(
                        "USB connections and file interactions will generate alerts in the alert management system."
                    )
                    print("You can manage these alerts through the Alert Management menu.")

                    monitor = PortMonitor()
                    monitoring_thread = threading.Thread(
                        target=monitor.start_monitoring,
                        args=(False,),  
                    )
                    monitoring_thread.daemon = True
                    monitoring_thread.start()
                    print("\n✅ USB port monitoring started")
                else:
                    print("\nUSB port monitoring is already running")

            elif choice == "2":
                if monitor and hasattr(monitor, "running") and monitor.running:
                    monitor.stop_monitoring()
                    print("\n✅ USB port monitoring stopped")
                else:
                    print("\nUSB port monitoring is not running")

            elif choice == "3":
                print("\n=== Connected USB Devices ===")
                list_connected_usb_devices()

            elif choice == "4":
                print("\n=== Available COM Ports ===")
                ports = list_available_ports()
                if not ports:
                    print("No COM ports available")

            elif choice == "5":
                alerts = client.get_port_alerts(include_handled=False)
                if not alerts:
                    print("\nNo active USB alerts found")
                else:
                    print("\n=== USB Alerts ===")
                    for i, alert in enumerate(alerts, 1):
                        print(f"\n{i}. Type: {alert.get('type', 'Unknown')}")
                        print(f"   Severity: {alert.get('severity', 'Medium')}")
                        print(f"   Time: {alert.get('timestamp', 'Unknown')}")
                        print(f"   Message: {alert.get('message', 'No message')}")

                        if "device_name" in alert:
                            print(f"   Device: {alert.get('device_name', 'Unknown')}")
                        if "device_id" in alert:
                            print(f"   Device ID: {alert.get('device_id', 'Unknown')}")

                    handle = input("\nWould you like to handle an alert? (y/n): ")
                    if handle.lower() == "y":
                        try:
                            alert_num = int(input("\nEnter alert number to handle: ")) - 1
                            if 0 <= alert_num < len(alerts):
                                print("\nSelect action:")
                                print("1. Dismiss")
                                print("2. Send Email Notification")
                                action = input("Enter choice: ")

                                action_type = "dismiss" if action == "1" else "email"
                                if client.handle_port_alert(alert_num, action_type):
                                    print(f"\nAlert {action_type}ed successfully")
                                else:
                                    print("\nFailed to handle alert")
                        except ValueError:
                            print("\nInvalid input. Please enter a number")

            elif choice == "6":
                if monitor and hasattr(monitor, "running") and monitor.running:
                    monitor.stop_monitoring()
                break
    except KeyboardInterrupt:
        print("\n\nMonitoring interrupted. Cleaning up...")
        if monitor and hasattr(monitor, "running") and monitor.running:
            monitor.stop_monitoring()
        print("Returning to previous menu...")
    except Exception as e:
        print(f"\nError in device monitoring: {str(e)}")
        if monitor and hasattr(monitor, "running") and monitor.running:
            monitor.stop_monitoring()
    finally:
        if monitor and hasattr(monitor, "running") and monitor.running:
            monitor.stop_monitoring()


def display_alerts(alerts, alert_type="System"):
    if not alerts:
        print(f"\nNo {alert_type.lower()} alerts found")
        return

    print(f"\n=== {alert_type} Alerts ===")
    for i, alert in enumerate(alerts, 1):
        print(f"\n{i}. Type: {alert.get('type', 'Unknown')}")
        print(f"   Severity: {alert.get('severity', 'Medium')}")
        if "username" in alert:
            print(f"   User: {alert['username']}")
        if "source_ip" in alert:
            print(f"   Source IP: {alert['source_ip']}")
        print(f"   Time: {alert.get('timestamp', 'Unknown')}")
        print(f"   Message: {alert.get('message', 'No message')}")
        if alert.get("handled", False):
            print("   Status: Handled")
        else:
            print("   Status: Active")


def unified_alert_menu(client):
    while True:
        print("\n=== Alert Management ===")
        print("1. View System Alerts")
        print("2. View Port Alerts")
        print("3. Handle System Alert")
        print("4. Handle Port Alert")
        print("5. Back")

        choice = input("\nEnter choice: ")

        if choice == "1":
            alerts = client.get_alerts(include_handled=False)
            display_alerts(alerts, alert_type="System")
        elif choice == "2":
            alerts = client.get_port_alerts(include_handled=False)
            display_alerts(alerts, alert_type="Port")
        elif choice == "3":
            alerts = client.get_alerts(include_handled=False)
            if not alerts:
                print("\nNo active system alerts")
                continue

            display_alerts(alerts, alert_type="System")
            handle_alert(client, alerts, "system")

        elif choice == "4":
            alerts = client.get_port_alerts(include_handled=False)
            if not alerts:
                print("\nNo active port alerts")
                continue

            display_alerts(alerts, alert_type="Port")
            handle_alert(client, alerts, "port")
        elif choice == "5":
            break


def handle_alert(client, alerts, alert_type="system"):
    """Generic function to handle different types of alerts"""
    try:
        alert_num = int(input("\nEnter alert number to handle (0 to cancel): ")) - 1
        if alert_num < 0:
            return

        print("\nSelect action:")
        print("1. Dismiss")
        print("2. Send Email Notification")
        action = input("Enter choice: ")

        action_type = "dismiss" if action == "1" else "email"

        if alert_type == "system":
            if client.handle_alert(alert_num, action_type):
                print(f"\nAlert {action_type}ed successfully")
        elif alert_type == "port":
            if client.handle_port_alert(alert_num, action_type):
                print(f"\nPort alert {action_type}ed successfully")
    except ValueError:
        print("\nInvalid input")


def user_activity_menu(client):
    while True:
        print("\n=== User Activity Monitor ===")
        print("1. View Active Users")
        print("2. View User Actions History")
        print("3. Back")

        choice = input("\nEnter choice: ")

        if choice == "1":
            try:
                active_users = client.get_active_users()
                if not active_users:
                    print("\nNo active users")
                    continue

                print("\nActive Users and Sessions:")
                for username, session in active_users.items():
                    print(f"\n=== User: {username} ===")
                    print(f"Session started: {session.get('start_time', 'Unknown')}")
                    print(f"Status: {session.get('status', 'Unknown')}")
                    print(f"Session ID: {session.get('session_id', 'Unknown')}")

                    actions = client.get_user_actions(username)
                    if actions:
                        print("\nRecent Actions:")
                        for action in actions[-3:]:
                            print(
                                f"- {action['timestamp']}: {action['action']} on {action['filepath']}"
                            )
            except Exception as e:
                print(f"\nError retrieving user data: {str(e)}")
                logger.error(f"Error in user activity menu: {str(e)}", exc_info=True)

        elif choice == "2":
            active_users = client.get_active_users()
            if not active_users:
                print("\nNo users to display")
                continue

            print("\nSelect user to view detailed action history:")
            users = list(active_users.keys())
            for i, username in enumerate(users, 1):
                print(f"{i}. {username}")

            try:
                choice = int(input("\nEnter user number (0 to cancel): "))
                if choice == 0:
                    continue
                if 1 <= choice <= len(users):
                    username = users[choice - 1]
                    actions = client.get_user_actions(username)
                    if not actions:
                        print(f"\nNo actions recorded for {username}")
                        continue

                    print(f"\n=== Action History for {username} ===")
                    for action in actions:
                        print(f"\nTimestamp: {action['timestamp']}")
                        print(f"Action: {action['action']}")
                        print(f"File: {action['filepath']}")
                        print(f"Status: {action['status']}")
            except ValueError:
                print("\nInvalid input. Please enter a number.")

        elif choice == "3":
            break


def file_monitoring_menu(client):
    while True:
        print("\n=== File Monitoring ===")
        print("1. View Monitored Folders")
        print("2. Add Folder to Monitor")
        print("3. View File Transfer History")
        print("4. Monitor Specific File")
        print("5. Back")

        choice = input("\nEnter choice: ")

        if choice == "1":
            print("\nDefault Monitored Folders:")
            print("- confidential (Source folder)")
            print("- destination (Target folder)")

            custom_folders = client.get_monitored_folders()
            if custom_folders:
                print("\nAdditional Monitored Folders:")
                for folder in custom_folders:
                    print(f"- {folder}")
                    try:
                        if os.path.exists(folder):
                            files = os.listdir(folder)
                            for file in files:
                                print(f"  └─ {file}")
                    except Exception as e:
                        print(f"  └─ Error accessing folder: {str(e)}")

        elif choice == "2":
            print("\nAdd New Folder to Monitor")
            folder_path = input("Enter full folder path: ").strip()

            if not folder_path:
                print("Invalid folder path")
                continue

            if not os.path.exists(folder_path):
                create = input("Folder doesn't exist. Create it? (y/n): ").lower()
                if create == "y":
                    try:
                        os.makedirs(folder_path)
                    except Exception as e:
                        print(f"Error creating folder: {str(e)}")
                        continue
                else:
                    continue

            if client.add_monitored_folder(folder_path):
                print(f"\nSuccessfully added {folder_path} to monitored folders")
            else:
                print("\nFailed to add folder to monitoring list")

        elif choice == "3":
            transfers = client.get_file_transfers()
            if transfers:
                print("\nRecent File Transfer History:")
                for transfer in transfers:
                    print(f"\nTimestamp: {transfer['timestamp']}")
                    print(f"From: {transfer['source']}")
                    print(f"To: {transfer['destination']}")
                    print(f"User: {transfer['username']}")
            else:
                print("\nNo file transfers have been recorded")

        elif choice == "4":
            files = client.list_files()
            if not files:
                print("\nNo files available to monitor")
                continue

            print("\nAvailable Files:")
            for i, file in enumerate(files, 1):
                print(f"{i}. {file}")

            try:
                file_choice = int(
                    input("\nSelect file number to monitor (0 to cancel): ")
                )
                if file_choice == 0:
                    continue
                if 1 <= file_choice <= len(files):
                    selected_file = files[file_choice - 1]
                    print(f"\nMonitoring {selected_file}")
                    print("Press Ctrl+C to stop monitoring")
                    try:
                        last_check = None
                        while True:
                            modifications = client.check_file_modifications(
                                selected_file
                            )
                            if modifications and modifications != last_check:
                                last_check = modifications
                                print(f"\nModification detected on {selected_file}:")
                                print(f"Type: {modifications['type']}")
                                print(f"Time: {modifications['timestamp']}")
                                print(f"User: {modifications['username']}")
                            time.sleep(1)
                    except KeyboardInterrupt:
                        print("\nStopped monitoring file")
            except ValueError:
                print("\nInvalid input. Please enter a number")

        elif choice == "5":
            break


def file_encryption_menu(client):
    while True:
        print("\n=== File Encryption Management ===")
        print("1. View Files")
        print("2. Encrypt File")
        print("3. Decrypt File")
        print("4. View Encryption Keys")
        print("5. View Access Requests")
        print("6. Back")

        choice = input("\nEnter choice: ")

        if choice == "1":
            files = client.list_files()
            if not files:
                print("\nNo files found")
            else:
                print("\nAvailable Files:")
                for i, file in enumerate(files, 1):
                    encrypted = check_file_encryption_status(file)
                    status = "\033[91m[ENCRYPTED]\033[0m" if encrypted else ""
                    print(f"{i}. {file} {status}")

        elif choice == "2":
            files = client.list_files()
            if not files:
                print("\nNo files available to encrypt.")
                continue

            print("\nAvailable Files:")
            for i, file in enumerate(files, 1):
                print(f"{i}. {file}")
            file_choice = input("\nSelect file number to encrypt (0 to cancel): ")

            try:
                file_choice = int(file_choice)
                if file_choice == 0:
                    continue
                if 1 <= file_choice <= len(files):
                    selected_file = os.path.join("confidential", files[file_choice - 1])
                    key = client.encrypt_file(selected_file)
                    if key:
                        print("\nFile encrypted successfully!")
                        print(f"Encryption key: {key}")
                    else:
                        print("\nFailed to encrypt file.")
            except ValueError:
                print("\nInvalid input. Please enter a number.")

        elif choice == "3":
            files = client.list_files()
            if not files:
                print("\nNo files available to decrypt.")
                continue

            print("\nAvailable Files:")
            for i, file in enumerate(files, 1):
                print(f"{i}. {file}")
            file_choice = input("\nSelect file number to decrypt (0 to cancel): ")

            try:
                file_choice = int(file_choice)
                if file_choice == 0:
                    continue
                if 1 <= file_choice <= len(files):
                    selected_file = os.path.join("confidential", files[file_choice - 1])
                    key = input("Enter decryption key: ")
                    if client.decrypt_file(selected_file, key):
                        print("\nFile decrypted successfully!")
                    else:
                        print(
                            "\nFailed to decrypt file. Invalid key or corrupted file."
                        )
            except ValueError:
                print("\nInvalid input. Please enter a number.")

        elif choice == "4":
            keys = client.get_keys()
            if not keys or len(keys) == 0:
                print("\nNo encryption keys found.")
            else:
                print("\n=== Encryption Keys ===")
                try:
                    for filename, data in keys.items():
                        if isinstance(data, dict) and "key" in data and "date" in data:
                            print(f"\nFile: {filename}")
                            print(f"Key: {data['key']}")
                            print(f"Date: {data['date']}")
                except Exception as e:
                    print(f"\nError displaying keys: {str(e)}")
                    print("Raw keys data:", keys)

        elif choice == "5":
            pending = client.get_pending_requests()
            if not pending:
                print("\nNo pending access requests.")
                continue

            print("\n=== Pending Access Requests ===")
            for i, req in enumerate(pending, 1):
                print(f"{i}. User: {req['username']} - File: {req['filename']}")

            req_choice = input("\nSelect request number to approve (0 to cancel): ")

            try:
                req_choice = int(req_choice)
                if req_choice == 0:
                    continue
                if 1 <= req_choice <= len(pending):
                    req = pending[req_choice - 1]
                    if client.approve_request(req["username"], req["filename"]):
                        print("\nRequest approved successfully!")
                    else:
                        print("\nFailed to approve request.")
            except ValueError:
                print("\nInvalid input. Please enter a number.")

        elif choice == "6":
            break


def run_network_monitor():
    print("\n=== Running Network Monitor ===")
    print("Starting Google Drive monitoring...")
    print("Press Ctrl+C to stop the Network Monitor")
    
    try:
        import network_test
        network_test.monitor_google_drive()
    except KeyboardInterrupt:
        print("\nNetwork Monitor stopped")
    except Exception as e:
        print(f"\nError running network Monitor: {str(e)}")

def user_management_menu(client):
    while True:
        print("\n=== User Management ===")
        print("1. View All Users")
        print("2. Block User")
        print("3. Unblock User")
        print("4. Back")
        
        choice = input("\nEnter choice: ")
        
        if choice == "1":
            users = client.get_all_users()
            if not users:
                print("\nNo users found or error retrieving users")
                continue
                
            print("\n=== User List ===")
            for i, user in enumerate(users, 1):
                status = "🟢 Active" if user.get("active") else "⚪ Inactive"
                block_status = "🔴 BLOCKED" if user.get("blocked") else "🟢 Permitted"
                print(f"{i}. {user['username']} - {status} [ {block_status} ]")
        
        elif choice == "2":
            users = client.get_all_users()
            if not users:
                print("\nNo users found or error retrieving users")
                continue
                
            print("\n=== Select User to Block ===")
            active_users = [user for user in users if not user.get("blocked")]
            
            if not active_users:
                print("\nNo active (unblocked) users found")
                continue
                
            for i, user in enumerate(active_users, 1):
                status = "🟢 Active" if user.get("active") else "⚪ Inactive"
                print(f"{i}. {user['username']} - {status}")
            
            try:
                user_choice = int(input("\nEnter user number to block (0 to cancel): "))
                if user_choice == 0:
                    continue
                    
                if 1 <= user_choice <= len(active_users):
                    username = active_users[user_choice-1]["username"]
                    confirm = input(f"\nAre you sure you want to block {username}? (y/n): ")
                    
                    if confirm.lower() == 'y':
                        if client.block_user(username):
                            print(f"\n✅ User {username} has been blocked successfully")
                        else:
                            print(f"\n❌ Failed to block user {username}")
                else:
                    print("\nInvalid selection")
            except ValueError:
                print("\nInvalid input. Please enter a number.")
        
        elif choice == "3":
            users = client.get_all_users()
            if not users:
                print("\nNo users found or error retrieving users")
                continue
                
            print("\n=== Select User to Unblock ===")
            blocked_users = [user for user in users if user.get("blocked")]
            
            if not blocked_users:
                print("\nNo blocked users found")
                continue
                
            for i, user in enumerate(blocked_users, 1):
                print(f"{i}. {user['username']}")
            
            try:
                user_choice = int(input("\nEnter user number to unblock (0 to cancel): "))
                if user_choice == 0:
                    continue
                    
                if 1 <= user_choice <= len(blocked_users):
                    username = blocked_users[user_choice-1]["username"]
                    if client.unblock_user(username):
                        print(f"\n✅ User {username} has been unblocked successfully")
                    else:
                        print(f"\n❌ Failed to unblock user {username}")
                else:
                    print("\nInvalid selection")
            except ValueError:
                print("\nInvalid input. Please enter a number.")
                
        elif choice == "4":
            break

def admin_menu(client):
    try:
        while True:
            print("\n=== Admin Dashboard ===")
            print("1. File Encryption Management")
            print("2. File Monitoring")
            print("3. User Activity Monitor")
            print("4. Port USB Monitoring")
            print("5. Alert Management")
            print("6. Network Monitoring")
            print("7. User Management")
            print("8. Logout")

            try:
                admin_choice = input("\nEnter choice: ")
            except KeyboardInterrupt:
                print("\n\nAdmin session interrupted. Logging out...")
                break

            if admin_choice == "1":
                file_encryption_menu(client)

            elif admin_choice == "2":
                file_monitoring_menu(client)

            elif admin_choice == "3":
                user_activity_menu(client)

            elif admin_choice == "4":
                external_device_monitoring_menu(client)

            elif admin_choice == "5":
                unified_alert_menu(client)
                
            elif admin_choice == "6":
                run_network_monitor()
                
            elif admin_choice == "7":
                user_management_menu(client)

            elif admin_choice == "8":
                print("\nLogging out from admin session...")
                break
    except KeyboardInterrupt:
        print("\n\nAdmin session interrupted. Logging out...")
    except Exception as e:
        print(f"\nError in admin menu: {str(e)}")
        logger.error(f"Error in admin menu: {str(e)}", exc_info=True)


def user_menu(client):
    try:
        while True:
            print("\n=== User Dashboard ===")
            print("1. View Available Files")
            print("2. Request File Access")
            print("3. Decrypt File")
            print("4. Logout")

            try:
                user_choice = input("\nEnter choice: ")
            except KeyboardInterrupt:
                print("\n\nUser session interrupted. Logging out...")
                break

            if user_choice == "1":
                files = client.list_files()
                if not files:
                    print("\nNo files found")
                else:
                    print("\nAvailable Files:")
                    for i, file in enumerate(files, 1):
                        encrypted = check_file_encryption_status(file)
                        status = "\033[91m[ENCRYPTED]\033[0m" if encrypted else ""
                        print(f"{i}. {file} {status}")

            elif user_choice == "2":
                files = client.list_files()
                if not files:
                    print("\nNo files available to request.")
                    continue

                print("\nAvailable Files:")
                for i, file in enumerate(files, 1):
                    print(f"{i}. {file}")
                file_choice = input("\nSelect file number to request (0 to cancel): ")

                try:
                    file_choice = int(file_choice)
                    if file_choice == 0:
                        continue
                    if 1 <= file_choice <= len(files):
                        selected_file = files[file_choice - 1]
                        key = client.request_file_access(selected_file)
                        if key:
                            print("\nAccess granted!")
                            print(f"Decryption key: {key}")
                        else:
                            print("\nAccess request failed or denied.")
                except ValueError:
                    print("\nInvalid input. Please enter a number.")

            elif user_choice == "3":
                files = client.list_files()
                if not files:
                    print("\nNo files available to decrypt.")
                    continue

                print("\nAvailable Files:")
                encrypted_files = []
                for i, file in enumerate(files, 1):
                    if check_file_encryption_status(file):
                        encrypted_files.append(file)
                
                if not encrypted_files:
                    print("\nNo encrypted files available to decrypt.")
                    continue
                    
                for i, file in enumerate(encrypted_files, 1):
                    print(f"{i}. {file}")
                file_choice = input("\nSelect file number to decrypt (0 to cancel): ")

                try:
                    file_choice = int(file_choice)
                    if file_choice == 0:
                        continue
                    if 1 <= file_choice <= len(files):
                        selected_file = os.path.join("confidential", files[file_choice - 1])
                        key = input("Enter decryption key: ")
                        if client.decrypt_file(selected_file, key):
                            print("\nFile decrypted successfully!")
                        else:
                            print(
                                "\nFailed to decrypt file. Invalid key or corrupted file."
                            )
                except ValueError:
                    print("\nInvalid input. Please enter a number.")

            elif user_choice == "4":
                print("\nLogging out from user session...")
                break
    except KeyboardInterrupt:
        print("\n\nUser session interrupted. Logging out...")
    except Exception as e:
        print(f"\nError in user menu: {str(e)}")
        logger.error(f"Error in user menu: {str(e)}", exc_info=True)


def graceful_shutdown():
    """Clean up resources before exit"""
    # Use a global variable to track if shutdown has already been performed
    global _shutdown_performed
    
    # Only perform shutdown once
    if not globals().get('_shutdown_performed', False):
        print("\nPerforming graceful shutdown...")
        
        # Log the shutdown
        logger.info("Application shutdown initiated")
        
        # Mark shutdown as performed
        globals()['_shutdown_performed'] = True


def main():
    # Initialize shutdown tracking
    globals()['_shutdown_performed'] = False
    
    if not os.path.exists("confidential"):
        os.makedirs("confidential")
        logger.info("Created confidential directory")

    if not os.path.exists("logs"):
        os.makedirs("logs")
        logger.info("Created logs directory")

    try:
        while True:
            print("\n=== DLP System Login ===")
            print("1. Admin Login")
            print("2. User Login")
            print("3. Exit")

            try:
                choice = input("\nEnter choice: ")
            except KeyboardInterrupt:
                print("\n\nProgram interrupted. Shutting down...")
                graceful_shutdown()
                break

            if choice == "1" or choice == "2":
                username = input("Username: ")
                password = input("Password: ")

                if username.strip() == "" or password.strip() == "":
                    print("\nError: Username and password cannot be empty!")
                    continue

                try:
                    client = UserClient()
                except ConnectionRefusedError:
                    print(
                        "\nCould not connect to server. Please ensure the server is running."
                    )
                    continue
                except Exception as e:
                    print(f"\nConnection error: {str(e)}")
                    continue

                if choice == "1":
                    try:
                        login_result = client.admin_login(username, password)
                        if login_result["status"] == "success":
                            print(f"\nWelcome Admin {username}!")
                            admin_menu(client)
                        else:
                            print("\nError: Invalid admin credentials!")
                    except Exception as e:
                        print(f"\nLogin error: {str(e)}")
                else:
                    try:
                        login_result = client.user_login(username, password)
                        if login_result == True:
                            print(f"\nWelcome User {username}!")
                            user_menu(client)
                        elif login_result != "blocked":  
                            print("\nError: Invalid user credentials!")
                    except Exception as e:
                        print(f"\nLogin error: {str(e)}")

            elif choice == "3":
                print("\nShutting down DLP system...")
                break
            else:
                print("\nInvalid choice! Please select 1, 2, or 3.")
    except KeyboardInterrupt:
        print("\n\nProgram interrupted. Shutting down...")
        graceful_shutdown()
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")
        logger.error(f"Unexpected error in main: {str(e)}", exc_info=True)
        graceful_shutdown()
    finally:
        graceful_shutdown()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProgram interrupted. Shutting down...")
        graceful_shutdown()
    except Exception as e:
        print(f"\nFatal error: {str(e)}")
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        graceful_shutdown()

