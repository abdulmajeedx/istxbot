import os
import base64
from pathlib import Path
from typing import Optional, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)


class CryptoError(Exception):
    pass


class CryptoManager:
    """Manages encryption and decryption of sensitive data"""
    
    def __init__(self, key_file: str = ".encryption_key"):
        self.key_file = Path(key_file)
        self.key = self._load_or_generate_key()
        self.cipher = Fernet(self.key)
    
    def _generate_key(self) -> bytes:
        """Generate a new encryption key"""
        return Fernet.generate_key()
    
    def _derive_key_from_password(self, password: str, salt: bytes) -> bytes:
        """Derive key from password using PBKDF2"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def _load_or_generate_key(self) -> bytes:
        """Load existing key or generate new one"""
        if self.key_file.exists():
            try:
                with open(self.key_file, 'rb') as f:
                    key = f.read()
                logger.info("Loaded existing encryption key")
                return key
            except Exception as e:
                logger.error(f"Error loading key: {e}")
                logger.warning("Generating new key")
        
        key = self._generate_key()
        self._save_key(key)
        logger.info("Generated and saved new encryption key")
        return key
    
    def _save_key(self, key: bytes):
        """Save encryption key to file"""
        try:
            os.makedirs(self.key_file.parent, exist_ok=True)
            with open(self.key_file, 'wb') as f:
                f.write(key)
            os.chmod(self.key_file, 0o600)
            logger.debug("Saved encryption key")
        except Exception as e:
            logger.error(f"Error saving key: {e}")
            raise CryptoError(f"Failed to save encryption key: {e}")
    
    def encrypt(self, data: Union[str, bytes]) -> str:
        """
        Encrypt data
        
        Args:
            data: Data to encrypt (string or bytes)
            
        Returns:
            Encrypted data as base64 string
            
        Raises:
            CryptoError: If encryption fails
        """
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            encrypted = self.cipher.encrypt(data)
            return base64.urlsafe_b64encode(encrypted).decode('utf-8')
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise CryptoError(f"Encryption failed: {e}")
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt data
        
        Args:
            encrypted_data: Encrypted data as base64 string
            
        Returns:
            Decrypted data as string
            
        Raises:
            CryptoError: If decryption fails
        """
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            decrypted = self.cipher.decrypt(encrypted_bytes)
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise CryptoError(f"Decryption failed: {e}")
    
    def encrypt_dict(self, data: dict, keys_to_encrypt: list = None) -> dict:
        """
        Encrypt specific keys in a dictionary
        
        Args:
            data: Dictionary containing sensitive data
            keys_to_encrypt: List of keys to encrypt (default: all)
            
        Returns:
            Dictionary with encrypted values
        """
        if keys_to_encrypt is None:
            keys_to_encrypt = list(data.keys())
        
        encrypted_dict = data.copy()
        for key in keys_to_encrypt:
            if key in encrypted_dict and encrypted_dict[key]:
                try:
                    encrypted_dict[key] = self.encrypt(str(encrypted_dict[key]))
                except CryptoError as e:
                    logger.warning(f"Failed to encrypt key '{key}': {e}")
        
        return encrypted_dict
    
    def decrypt_dict(self, data: dict, keys_to_decrypt: list = None) -> dict:
        """
        Decrypt specific keys in a dictionary
        
        Args:
            data: Dictionary containing encrypted data
            keys_to_decrypt: List of keys to decrypt (default: all)
            
        Returns:
            Dictionary with decrypted values
        """
        if keys_to_decrypt is None:
            keys_to_decrypt = list(data.keys())
        
        decrypted_dict = data.copy()
        for key in keys_to_decrypt:
            if key in decrypted_dict and decrypted_dict[key]:
                try:
                    decrypted_dict[key] = self.decrypt(str(decrypted_dict[key]))
                except CryptoError as e:
                    logger.warning(f"Failed to decrypt key '{key}': {e}")
        
        return decrypted_dict


class EnvEncryptor:
    """Encrypts/decrypts environment variables"""
    
    def __init__(self, crypto_manager: Optional[CryptoManager] = None):
        self.crypto = crypto_manager or CryptoManager()
        self.encrypted_marker = "ENC:"
    
    def encrypt_value(self, value: str) -> str:
        """
        Encrypt an environment variable value
        
        Args:
            value: Plain text value
            
        Returns:
            Marked encrypted value (e.g., "ENC:<encrypted_base64>")
        """
        encrypted = self.crypto.encrypt(value)
        return f"{self.encrypted_marker}{encrypted}"
    
    def decrypt_value(self, value: str) -> str:
        """
        Decrypt an environment variable value
        
        Args:
            value: Encrypted or plain text value
            
        Returns:
            Decrypted plain text value
        """
        if value.startswith(self.encrypted_marker):
            encrypted = value[len(self.encrypted_marker):]
            return self.crypto.decrypt(encrypted)
        return value
    
    def encrypt_env_file(self, input_file: str = ".env", output_file: str = ".env.encrypted"):
        """
        Encrypt all values in .env file
        
        Args:
            input_file: Input .env file path
            output_file: Output encrypted .env file path
        """
        try:
            with open(input_file, 'r') as f:
                lines = f.readlines()
            
            encrypted_lines = []
            for line in lines:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.split('=', 1)
                    encrypted_value = self.encrypt_value(value.strip())
                    encrypted_lines.append(f"{key}={encrypted_value}\n")
                else:
                    encrypted_lines.append(line)
            
            with open(output_file, 'w') as f:
                f.writelines(encrypted_lines)
            
            os.chmod(output_file, 0o600)
            logger.info(f"Encrypted {input_file} to {output_file}")
        except Exception as e:
            logger.error(f"Error encrypting env file: {e}")
            raise CryptoError(f"Failed to encrypt env file: {e}")
    
    def load_decrypted_env(self, env_file: str = ".env.encrypted"):
        """
        Load and decrypt environment variables from encrypted file
        
        Args:
            env_file: Encrypted .env file path
            
        Returns:
            Dict of decrypted environment variables
        """
        env_vars = {}
        try:
            with open(env_file, 'r') as f:
                lines = f.readlines()
            
            for line in lines:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = self.decrypt_value(value.strip())
            
            logger.info(f"Loaded and decrypted {len(env_vars)} environment variables")
        except Exception as e:
            logger.error(f"Error loading decrypted env: {e}")
            raise CryptoError(f"Failed to load decrypted env: {e}")
        
        return env_vars


_global_crypto_manager: Optional[CryptoManager] = None


def get_crypto_manager() -> CryptoManager:
    """Get global crypto manager instance"""
    global _global_crypto_manager
    if _global_crypto_manager is None:
        _global_crypto_manager = CryptoManager()
    return _global_crypto_manager


def encrypt_sensitive_data(data: str) -> str:
    """Encrypt sensitive data using global crypto manager"""
    return get_crypto_manager().encrypt(data)


def decrypt_sensitive_data(data: str) -> str:
    """Decrypt sensitive data using global crypto manager"""
    return get_crypto_manager().decrypt(data)
