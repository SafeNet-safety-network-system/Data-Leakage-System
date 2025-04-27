import json
import wmi
import time
import os
import win32file
import socket
import subprocess
import serial.tools.list_ports
import requests
import pythoncom  # Add this import for COM initialization
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime

# Email notification configuration
MAILGUN_API_KEY = "320690068d6b18741d8abd1af4d85a0c-ac3d5f74-f06a6839"
MAILGUN_DOMAIN = "sandboxa3628d82a4714395ba7eeea5179f413c.mailgun.org"
TO_EMAIL = "atharvkulkarni2002@gmail.com"
FROM_EMAIL = f"no-reply@{MAILGUN_DOMAIN}"
WATCH_FOLDER = r"confidential"
DESTINATION_FOLDER = r"destination"


def get_current_time():
    """Returns the current date and time in a readable format."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_system_ip():
    """Gets the IP address of the source system."""
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception as e:
        return f"Error retrieving IP: {e}"


def get_external_device_ip():
    """Finds the IP of an externally connected device if it's a network device."""
    try:
        output = subprocess.check_output("ipconfig /all", shell=True).decode()
        lines = output.split("\n")
        for line in lines:
            if "IPv4 Address" in line or "Default Gateway" in line:
                return line.split(":")[-1].strip()
        return "No external IP found"
    except Exception as e:
        return f"Error retrieving external device IP: {e}"


def send_email_notification(subject, message_body):
    """Send email via Mailgun with USB device alerts."""
    print(f"📧 Sending email alert: {subject}")  # Debug log

    try:
        response = requests.post(
            f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
            auth=("api", MAILGUN_API_KEY),
            data={
                "from": FROM_EMAIL,
                "to": TO_EMAIL,
                "subject": subject,
                "text": message_body,
            },
        )

        # Debug: Check Mailgun response
        if response.status_code == 200:
            print("✅ Email alert sent successfully!")
            return True
        else:
            print(
                f"❌ Failed to send email! Status Code: {response.status_code}, Response: {response.text}"
            )
            return False
    except Exception as e:
        print(f"❌ Email sending error: {str(e)}")
        return False


def get_usb_drive_letters():
    """Find all connected USB storage devices."""
    drives = [f"{d}:\\" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
    usb_drives = [
        drive
        for drive in drives
        if win32file.GetDriveType(drive) == win32file.DRIVE_REMOVABLE
    ]
    return usb_drives


def list_available_ports():
    """Lists available COM ports and their status."""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("❌ No available ports found.")
        return []

    available_ports = []
    print("\n🔍 Checking available COM ports...")
    for port in ports:
        print(
            f"🛠 Port: {port.device} | Description: {port.description} | Status: {'Available' if port.device else 'In Use'}"
        )
        if port.device:
            available_ports.append(port.device)

    return available_ports


class USBFileCopyHandler(FileSystemEventHandler):
    """Detects file copies from system drive to USB drive."""

    def __init__(self, usb_drive):
        super().__init__()  # Add parent class initialization
        self.usb_drive = usb_drive
        self.source_ip = get_system_ip()
        self.port_monitor = None  # Will be set by PortMonitor

    def on_created(self, event):
        """Triggered when a file is copied to the USB device."""
        if not event.is_directory:
            copy_time = get_current_time()
            src_path = event.src_path
            dest_folder = os.path.dirname(src_path)
            print(f"📂 [{copy_time}] File Copied: {src_path} → {dest_folder}")
            
            # Create an alert for file transfer with HIGH severity
            if self.port_monitor:
                alert = self.port_monitor._add_alert(
                    "file_transfer",
                    f"File transfer detected: {os.path.basename(src_path)}",
                    "HIGH",
                    source_path=src_path,
                    destination_folder=dest_folder,
                    file_name=os.path.basename(src_path)
                )
                
                # Explicitly send email notification for file transfers regardless of email_notifications setting
                if not alert.get("emailed", False):
                    self.port_monitor._send_alert_email(alert)
                    alert["emailed"] = True
                    self.port_monitor._save_alerts()  # Save the updated alert status


def list_connected_usb_devices():
    """Lists all currently connected USB devices with specific properties."""
    try:
        c = wmi.WMI()
        devices = c.Win32_PnPEntity(ConfigManagerErrorCode=0)

        if not devices:
            print("❌ No USB devices are currently connected.")
        else:
            print("\n🔍 Listing currently connected USB devices...")
            for device in devices:
                if device.DeviceID.startswith(("USB", "USBSTOR")):
                    properties = {
                        "Name": device.Name,
                        "Description": device.Description,
                        "DeviceID": device.DeviceID,
                        "Manufacturer": device.Manufacturer,
                        "Status": device.Status,
                        "SystemName": device.SystemName,
                    }
                    print("\n" + "=" * 50)
                    for prop, value in properties.items():
                        if value:  # Only print if the property has a value
                            print(f"{prop}: {value}")
    except Exception as e:
        print(f"Error listing USB devices: {e}")


class PortMonitor:
    def __init__(self):
        self.running = False
        self.observer = None
        self.confidential_path = os.path.abspath("confidential")
        self.email_notifications = False
        self.last_notifications = {}  # To prevent duplicate emails
        self.alerts = []  # Store alerts for the system

        # Setup logging directory
        if not os.path.exists("logs"):
            os.makedirs("logs")

        # Initialize alerts from file if it exists
        self._load_alerts()

    def start_monitoring(self, email_notifications=True):  # Changed default to True
        """
        Start monitoring USB ports and devices
        """
        # Initialize COM for this thread
        pythoncom.CoInitializeEx(0)
        
        try:
            self.running = True
            self.email_notifications = email_notifications
            c = wmi.WMI()
            print("\n🚀 Starting USB monitoring...\n")
            print(f"📧 Email notifications {'enabled' if email_notifications else 'disabled'}")

            # Initial system setup
            print("📊 USB activity will be logged to the alert management system")

            # Step 1: List Connected USB Devices Before Monitoring Starts
            list_connected_usb_devices()

            # Step 2: Check Available Ports
            list_available_ports()

            print("\n👀 Listening for USB device connections...\n")
            print("Press Ctrl+C to stop monitoring")

            watcher_creation = c.Win32_PnPEntity.watch_for("creation")
            watcher_deletion = c.Win32_PnPEntity.watch_for("deletion")

            while self.running:
                try:
                    # Watch for new USB device connections
                    usb = watcher_creation(timeout_ms=1000)
                    if usb:
                        if usb.DeviceID.startswith(("USB", "USBSTOR")):
                            connection_time = get_current_time()
                            print(f"\n🔌 [{connection_time}] New USB Device Connected:")
                            # Display detailed device information
                            properties = {
                                "Name": usb.Name,
                                "Description": usb.Description,
                                "DeviceID": usb.DeviceID,
                                "Manufacturer": usb.Manufacturer,
                                "Status": usb.Status,
                                "SystemName": usb.SystemName,
                            }
                            for prop, value in properties.items():
                                if value:  # Only print if the property has a value
                                    print(f"{prop}: {value}")

                            # Create an alert for the system
                            self._add_alert(
                                "usb_connection",
                                f"USB Device Connected: {usb.Name if usb.Name else 'Unknown Device'}",
                                "HIGH",
                                device_id=usb.DeviceID,
                                device_name=usb.Name,
                                manufacturer=usb.Manufacturer,
                            )

                            # Check for interactions with confidential folder
                            time.sleep(2)  # Allow time for drive assignment
                            usb_drives = get_usb_drive_letters()
                            if usb_drives:
                                for drive in usb_drives:
                                    print(
                                        f"📂 [{connection_time}] USB Drive Detected: {drive}"
                                    )
                                    # Monitor for file copies between USB and confidential folder
                                    self._monitor_confidential_folder(drive)

                    # Watch for USB disconnection
                    usb = watcher_deletion(timeout_ms=1000)
                    if usb:
                        if usb.DeviceID.startswith(("USB", "USBSTOR")):
                            disconnection_time = get_current_time()
                            print(f"\n🔌 [{disconnection_time}] USB Device Disconnected:")
                            print(f"DeviceID: {usb.DeviceID}")

                            # Add disconnection alert
                            self._add_alert(
                                "usb_disconnection",
                                f"USB Device Disconnected: {usb.DeviceID}",
                                "INFO",
                                device_id=usb.DeviceID,
                            )

                except wmi.x_wmi_timed_out:
                    pass
                except KeyboardInterrupt:
                    print("\nMonitoring interrupted by user")
                    # Don't print stop message here, it will be handled by stop_monitoring()
                except Exception as e:
                    print(f"❌ [{get_current_time()}] Error: {e}")
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nMonitoring interrupted by user")
        except Exception as e:
            print(f"❌ Error in USB monitoring: {str(e)}")
        finally:
            # Clean up COM for this thread when done
            if self.observer:
                self.observer.stop()
                self.observer.join()
            
            # Save alerts when monitoring stops
            self._save_alerts()
            
            # Uninitialize COM
            try:
                pythoncom.CoUninitialize()
            except:
                pass
            
            # Only print this message if it wasn't stopped externally (by stop_monitoring)
            if self.running:
                print("\n🛑 USB monitoring stopped")
                
            self.running = False

    def _add_alert(self, alert_type, message, severity="MEDIUM", **kwargs):
        """Add a new alert to the system"""
        alert = {
            "type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": get_current_time(),
            "handled": False,
            "source_ip": get_system_ip(),
            "system": socket.gethostname(),
            **kwargs,
        }
        self.alerts.append(alert)
        self._save_alerts()  # Save alerts after adding new one
        
        # Automatically send email notification for HIGH severity alerts
        if severity == "HIGH" and self.email_notifications:
            self._send_alert_email(alert)
            alert["emailed"] = True
            self._save_alerts()  # Save the updated alert
        
        return alert

    def _load_alerts(self):
        """Load alerts from file"""
        try:
            if os.path.exists("logs/port_alerts.json"):
                with open("logs/port_alerts.json", "r") as f:
                    self.alerts = json.load(f)
            else:
                self.alerts = []
        except Exception as e:
            print(f"Error loading port alerts: {e}")
            self.alerts = []

    def _save_alerts(self):
        """Save alerts to file"""
        try:
            with open("logs/port_alerts.json", "w") as f:
                json.dump(self.alerts, f, indent=4)
        except Exception as e:
            print(f"Error saving port alerts: {e}")

    def get_alerts(self, include_handled=False):
        """Get port monitoring alerts"""
        if include_handled:
            return self.alerts
        return [alert for alert in self.alerts if not alert.get("handled")]

    def mark_alert_handled(self, alert_index, action="dismiss"):
        """Mark an alert as handled with optional email notification"""
        try:
            if 0 <= alert_index < len(self.alerts):
                alert = self.alerts[alert_index]

                # If action is email, send notification before marking handled
                if action == "email" and not alert.get("emailed", False):
                    self._send_alert_email(alert)
                    alert["emailed"] = True

                # Mark alert as handled
                self.alerts[alert_index]["handled"] = True
                self.alerts[alert_index]["handled_time"] = get_current_time()
                self.alerts[alert_index]["handled_action"] = action

                # Save alerts after updating
                self._save_alerts()
                return True
            return False
        except Exception as e:
            print(f"Error handling alert: {e}")
            return False

    def _send_alert_email(self, alert):
        """Send email for any type of port alert"""
        subject = f"🚨 USB Alert: {alert.get('type', 'Unknown')} ({alert.get('severity', 'Unknown')})"

        message_body = f"""
Security Alert from Port Monitoring System

Type: {alert.get('type', 'Unknown')}
Severity: {alert.get('severity', 'Unknown')}
Time: {alert.get('timestamp', 'Unknown')}

Message: {alert.get('message', 'No details available')}

System: {alert.get('system', socket.gethostname())}
System IP: {alert.get('source_ip', 'Unknown')}

"""

        # Add device details if available
        if "device_name" in alert:
            message_body += f"Device Name: {alert.get('device_name', 'Unknown')}\n"
        if "device_id" in alert:
            message_body += f"Device ID: {alert.get('device_id', 'Unknown')}\n"
        if "manufacturer" in alert:
            message_body += f"Manufacturer: {alert.get('manufacturer', 'Unknown')}\n"

        message_body += (
            "\nThis is an automated message from your DLP Port Monitoring System."
        )

        return send_email_notification(subject, message_body)

    def _monitor_confidential_folder(self, usb_drive):
        try:
            event_handler = USBFileCopyHandler(usb_drive)
            # Set the port_monitor reference so the handler can create alerts
            event_handler.port_monitor = self
            
            if self.observer:
                self.observer.stop()
                self.observer.join()  # Wait for the observer to stop completely
            self.observer = Observer()
            # Monitor both USB drive and confidential folder
            self.observer.schedule(event_handler, usb_drive, recursive=True)
            self.observer.schedule(
                event_handler, self.confidential_path, recursive=True
            )
            self.observer.start()
        except Exception as e:
            print(f"❌ Error setting up folder monitoring: {e}")

    def stop_monitoring(self):
        """Stop monitoring USB ports and devices"""
        if not self.running:
            print("\nMonitoring is not running")
            return
            
        # Set flag first to prevent duplicate messages
        self.running = False
        print("\n🛑 Port monitoring stopped")
        
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join()
            except Exception as e:
                print(f"Error stopping observer: {e}")

        # Add a system alert that monitoring was stopped
        self._add_alert("system", "USB Port Monitoring Stopped", "INFO")

        # Save alerts when stopping
        self._save_alerts()


if __name__ == "__main__":
    monitor = PortMonitor()
    try:
        monitor.start_monitoring(email_notifications=True)  # Changed to True to enable email notifications
    except KeyboardInterrupt:
        monitor.stop_monitoring()
