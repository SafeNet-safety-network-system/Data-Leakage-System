import os
from cryptography.fernet import Fernet
import json
from datetime import datetime
import logging


class EncryptionManager:
    def __init__(self):
        self.keys_file = "encryption_keys.json"
        self.logger = logging.getLogger("encryption")
        handler = logging.FileHandler("logs/encryption.log")
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.load_keys()

    def load_keys(self):
        try:
            if os.path.exists(self.keys_file):
                with open(self.keys_file, "r") as f:
                    self.keys = json.load(f)
                self.logger.info("Encryption keys loaded successfully")
            else:
                self.keys = {}
                self.logger.info("No existing keys file, creating new keys store")
        except Exception as e:
            self.logger.error(f"Error loading keys: {str(e)}", exc_info=True)
            self.keys = {}

    def save_keys(self):
        try:
            with open(self.keys_file, "w") as f:
                json.dump(self.keys, f)
            self.logger.info("Encryption keys saved successfully")
        except Exception as e:
            self.logger.error(f"Error saving keys: {str(e)}", exc_info=True)

    def encrypt_file(self, filename):
        try:
            # Get base filename for key storage
            base_filename = os.path.basename(filename)

            # Check if file already has a key
            if base_filename in self.keys:
                existing_key = self.keys[base_filename].get("key")
                if existing_key:
                    self.logger.info(f"Retrieved existing key for {base_filename}")
                    return existing_key

            # Generate new key and encrypt
            key = Fernet.generate_key()
            f = Fernet(key)

            with open(filename, "rb") as file:
                file_data = file.read()

            encrypted_data = f.encrypt(file_data)
            with open(filename, "wb") as file:
                file.write(encrypted_data)

            # Store key with base filename
            self.keys[base_filename] = {
                "key": key.decode(),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            self.save_keys()
            self.logger.info(f"File {base_filename} encrypted successfully")
            return key.decode()
        except Exception as e:
            self.logger.error(
                f"Error encrypting file {filename}: {str(e)}", exc_info=True
            )
            return None

    def decrypt_file(self, filename, key):
        try:
            f = Fernet(key.encode())
            base_filename = os.path.basename(filename)

            with open(filename, "rb") as file:
                encrypted_data = file.read()

            decrypted_data = f.decrypt(encrypted_data)
            with open(filename, "wb") as file:
                file.write(decrypted_data)

            if base_filename in self.keys:
                del self.keys[base_filename]
                self.save_keys()
                self.logger.info(
                    f"Removed encryption key for {base_filename} after decryption"
                )

            self.logger.info(f"File {base_filename} decrypted successfully")
            return True
        except Exception as e:
            self.logger.error(
                f"Decryption error for file {filename}: {str(e)}", exc_info=True
            )
            return False

    def get_all_keys(self):
        """Ensure keys are loaded before returning"""
        if not hasattr(self, "keys"):
            self.load_keys()
        return self.keys

    def clear_keys(self):
        self.keys = {}
        self.save_keys()
        self.logger.info("All encryption keys cleared")
