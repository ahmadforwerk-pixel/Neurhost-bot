"""Security module for token encryption and decryption."""

from cryptography.fernet import Fernet, InvalidToken
import logging

logger = logging.getLogger(__name__)


class SecretsManager:
    """
    Encrypt and decrypt secrets using Fernet (symmetric encryption).
    
    Encryption key stored in env var (never in code).
    Plaintext only exists in memory during use.
    """
    
    def __init__(self, encryption_key: str):
        """
        Initialize secrets manager.
        
        Args:
            encryption_key: Base64-encoded 32-byte Fernet key
        
        Raises:
            ValueError: If key is invalid
        """
        try:
            self.cipher = Fernet(encryption_key.encode())
        except Exception as e:
            raise ValueError(f"Invalid encryption key format: {e}")
    
    def encrypt_token(self, plaintext_token: str) -> str:
        """
        Encrypt plaintext token.
        
        Args:
            plaintext_token: Raw Telegram bot token
        
        Returns:
            Base64-encoded encrypted token (safe to store in DB)
        
        Raises:
            ValueError: If encryption fails
        """
        try:
            encrypted_bytes = self.cipher.encrypt(plaintext_token.encode('utf-8'))
            return encrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise ValueError(f"Encryption failed: {e}")
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """
        Decrypt token from database.
        
        Args:
            encrypted_token: Fernet-encrypted token from DB
        
        Returns:
            Plaintext token (use immediately, don't persist)
        
        Raises:
            ValueError: If token is corrupted or key is wrong
        """
        try:
            plaintext_bytes = self.cipher.decrypt(encrypted_token.encode('utf-8'))
            return plaintext_bytes.decode('utf-8')
        except InvalidToken:
            logger.error("Cannot decrypt token - key mismatch or corrupted data")
            raise ValueError("Cannot decrypt token - key mismatch or corrupted")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError(f"Decryption failed: {e}")
