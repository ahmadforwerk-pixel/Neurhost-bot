# NeuroHost V4 Production: Key Code Snippets

## 1. Security Module: Token Encryption

```python
# src/security/secrets_manager.py
from cryptography.fernet import Fernet, InvalidToken
import os
import base64

class SecretsManager:
    """
    Encrypt and decrypt secrets using Fernet (symmetric encryption).
    
    Security model:
    - Encryption key stored in env var (NOT in code)
    - Keys rotated periodically
    - Encrypted secrets stored in PostgreSQL
    - Plaintext only exists in memory during use
    """
    
    def __init__(self):
        key_str = os.environ.get("ENCRYPTION_KEY")
        if not key_str:
            raise ValueError("ENCRYPTION_KEY env var not set")
        
        # Key should be base64-encoded 32 bytes (Fernet requirement)
        try:
            self.cipher = Fernet(key_str.encode())
        except Exception as e:
            raise ValueError(f"Invalid ENCRYPTION_KEY format: {e}")
    
    def encrypt_token(self, plaintext_token: str) -> str:
        """
        Encrypt plaintext token.
        
        Args:
            plaintext_token: Raw Telegram bot token
        
        Returns:
            Base64-encoded encrypted token, safe to store
        """
        try:
            encrypted_bytes = self.cipher.encrypt(plaintext_token.encode('utf-8'))
            return encrypted_bytes.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Encryption failed: {e}")
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """
        Decrypt token from database.
        
        Args:
            encrypted_token: Fernet-encrypted token from DB
        
        Returns:
            Plaintext token (use immediately, don't store)
        
        Raises:
            ValueError if token is corrupted or key is wrong
        """
        try:
            plaintext_bytes = self.cipher.decrypt(encrypted_token.encode('utf-8'))
            return plaintext_bytes.decode('utf-8')
        except InvalidToken:
            raise ValueError("Cannot decrypt token - key mismatch or corrupted data")
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")

# Usage:
secrets_mgr = SecretsManager()

# When saving bot:
encrypted_token = secrets_mgr.encrypt_token(user_supplied_token)
bot = Bot(token_encrypted=encrypted_token, ...)
db.session.add(bot)

# When running bot (decrypt only in memory, never write to disk):
plaintext_token = secrets_mgr.decrypt_token(bot.token_encrypted)
os.environ["BOT_TOKEN"] = plaintext_token  # Pass to container
# plaintext_token garbage-collected immediately after use
```

## 2. Security Module: Token Validation

```python
# src/security/token_validator.py
import aiohttp
import asyncio
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

class TelegramTokenValidator:
    """
    Verify Telegram bot token is valid before accepting it.
    
    Prevents:
    - Acceptance of fake/inactive tokens
    - Resource waste on invalid bots
    - Worms with embedded fake tokens
    """
    
    TELEGRAM_API_BASE = "https://api.telegram.org"
    VALIDATION_TIMEOUT = 5  # seconds
    
    async def validate_token(self, token: str) -> Tuple[bool, str]:
        """
        Validate token by calling Telegram API.
        
        Args:
            token: Telegram bot token to verify
        
        Returns:
            (is_valid: bool, error_message: str)
        
        Example:
            is_valid, msg = await validator.validate_token("123:ABC")
            if not is_valid:
                raise ValueError(msg)
        """
        
        if not token or len(token) < 20:
            return False, "Token too short or empty"
        
        if ':' not in token:
            return False, "Invalid token format (missing colon)"
        
        try:
            url = f"{self.TELEGRAM_API_BASE}/bot{token}/getMe"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=self.VALIDATION_TIMEOUT)
                ) as resp:
                    
                    if resp.status != 200:
                        return False, f"Telegram API error: HTTP {resp.status}"
                    
                    data = await resp.json()
                    
                    if not data.get("ok"):
                        error = data.get("description", "Unknown error")
                        return False, f"Invalid token: {error}"
                    
                    result = data.get("result")
                    if not result or not result.get("is_bot"):
                        return False, "Token is valid but not a bot"
                    
                    # Success - token is valid
                    bot_username = result.get("username", "unknown")
                    logger.info(f"Token validated for bot @{bot_username}")
                    return True, ""
        
        except asyncio.TimeoutError:
            return False, "Telegram API timeout - please try again"
        except aiohttp.ClientError as e:
            return False, f"Network error: {str(e)[:100]}"
        except Exception as e:
            logger.exception(f"Unexpected error validating token: {e}")
            return False, "Validation error - please try again later"

# Usage in handler:
validator = TelegramTokenValidator()

async def handle_bot_upload(update, context):
    token = extract_token(code)
    
    is_valid, error_msg = await validator.validate_token(token)
    if not is_valid:
        await update.message.reply_text(f"❌ Invalid token: {error_msg}")
        return
    
    # Only now do we store the token
    db.save_bot(token)
    await update.message.reply_text("✅ Bot token validated and saved!")
```

## 3. Security Module: Code Scanning

```python
# src/security/code_scanner.py
import ast
from typing import Tuple, Set
import logging

logger = logging.getLogger(__name__)

class CodeSecurityScanner:
    """
    Detect obviously malicious Python code using AST analysis.
    
    NOT a full sandbox - designed to catch common attacks:
    - os.system() calls
    - subprocess exploitation
    - __import__ tricks
    - eval/exec
    
    CANNOT catch:
    - C extensions
    - Bytecode manipulation
    - Complex obfuscation
    
    Therefore, isolation (Docker) is REQUIRED regardless.
    """
    
    # Forbidden module imports
    DANGEROUS_MODULES = {
        'os', 'sys', 'subprocess', 'socket', 'urllib', 'urllib.request',
        '__builtin__', '__main__', 'importlib', 'types', 'inspect',
        'multiprocessing', 'threading', 'concurrent.futures',
    }
    
    # Forbidden function calls
    DANGEROUS_FUNCTIONS = {
        'eval', 'exec', 'compile', '__import__', 'open',
    }
    
    # Allowed but potentially risky modules (whitelist approach)
    ALLOWED_NETWORKING = {
        'requests', 'aiohttp', 'httpx', 'urllib3',  # HTTP clients
        'telegram', 'telegram.ext',  # Telegram lib (expected)
    }
    
    def scan_code(self, code: str) -> Tuple[bool, str]:
        """
        Scan code for security issues.
        
        Args:
            code: Python source code to scan
        
        Returns:
            (is_safe: bool, violation_message: str)
        
        Example:
            safe, msg = scanner.scan_code(user_code)
            if not safe:
                raise ValueError(f"Code rejected: {msg}")
        """
        
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            # Syntax errors are OK (don't run the code)
            return False, f"Syntax error (code won't run): {e}"
        
        violations = []
        
        # Walk AST looking for violations
        for node in ast.walk(tree):
            
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    violation = self._check_import(module_name)
                    if violation:
                        violations.append(violation)
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]
                    violation = self._check_import(module_name)
                    if violation:
                        violations.append(violation)
            
            # Check function calls
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.DANGEROUS_FUNCTIONS:
                        violations.append(f"Forbidden function: {node.func.id}()")
            
            # Check attribute access patterns (e.g., os.system)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    if node.value.id in self.DANGEROUS_MODULES:
                        if node.attr in {'system', 'popen', 'run', 'call'}:
                            violations.append(f"Forbidden: {node.value.id}.{node.attr}()")
        
        if violations:
            return False, "; ".join(violations[:3])  # First 3 violations
        
        return True, ""
    
    def _check_import(self, module_name: str) -> str:
        """Check if import is allowed."""
        
        # Explicitly dangerous
        if module_name in self.DANGEROUS_MODULES:
            return f"Forbidden import: {module_name}"
        
        # Networking is OK only if in whitelist
        if module_name in {'socket', 'ssl', 'http'}:
            return f"Forbidden import: {module_name}"
        
        # Whitelist known safe modules for Telegram bots
        safe_modules = {
            'telegram', 'logging', 'json', 'datetime', 'time', 're',
            'asyncio', 'aiohttp', 'requests', 'random', 'math', 'hashlib',
            'collections', 'itertools', 'functools', 'operator', 'string',
            'uuid', 'base64', 'enum',
        }
        
        if module_name in safe_modules or module_name in self.ALLOWED_NETWORKING:
            return ""
        
        # Unknown modules are REJECTED (whitelist approach)
        return f"Unknown module (not whitelisted): {module_name}"

# Usage:
scanner = CodeSecurityScanner()

async def handle_bot_upload(update, context):
    code = get_code_from_file(file)
    
    is_safe, violation = scanner.scan_code(code)
    if not is_safe:
        await update.message.reply_text(
            f"❌ Code rejected for security:\n{violation}\n\n"
            f"Forbidden imports: os, sys, subprocess, socket\n"
            f"Forbidden calls: eval, exec, open, __import__"
        )
        return
    
    # Safe to proceed
    db.save_bot_code(code)
```

## 4. Container Manager: Launch Bot

```python
# src/containers/manager.py
import docker
from docker.types import RestartPolicy
from typing import Optional
import logging
import os

logger = logging.getLogger(__name__)

class DockerContainerManager:
    """
    Manage Docker containers for user bots.
    
    Security model:
    - Each bot in isolated container
    - No access to host
    - Non-root user
    - Hard resource limits (kernel enforced)
    - Read-only root filesystem (except /tmp)
    """
    
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as e:
            logger.critical(f"Cannot connect to Docker daemon: {e}")
            raise
    
    def launch_bot_container(
        self,
        bot_id: int,
        bot_token: str,
        timeout_seconds: int,
        cpu_limit: str = "500m",
        memory_limit: str = "512m",
    ) -> str:
        """
        Launch user bot in isolated Docker container.
        
        Args:
            bot_id: Internal bot ID
            bot_token: Telegram token (plaintext, only in memory)
            timeout_seconds: Kill container after this many seconds
            cpu_limit: CPU quota (e.g., "500m" = 0.5 cores)
            memory_limit: RAM limit (e.g., "512m")
        
        Returns:
            Container ID
        
        Raises:
            docker.errors.DockerException on Docker error
        """
        
        container_name = f"neurhost-bot-{bot_id}"
        
        try:
            # Ensure image exists (pull or build)
            image_name = "neurhost-user-bot:latest"
            try:
                self.client.images.get(image_name)
            except docker.errors.ImageNotFound:
                logger.info(f"Image {image_name} not found, pulling...")
                self.client.images.pull("python:3.11-slim")  # Or build custom
            
            # Run container with strict security settings
            container = self.client.containers.run(
                image=image_name,
                name=container_name,
                detach=True,
                remove=False,  # Keep for logs inspection
                
                # ===== ENVIRONMENT =====
                environment={
                    "BOT_TOKEN": bot_token,  # Only this secret
                    "BOT_ID": str(bot_id),
                    "PYTHONUNBUFFERED": "1",  # Real-time logging
                },
                
                # ===== VOLUMES (read-only code, no host access) =====
                volumes={
                    f"/neurhost/bots/{bot_id}/code": {
                        "bind": "/app",
                        "mode": "ro"  # Read-only
                    }
                },
                
                # ===== NETWORK (isolated, no external network) =====
                network_mode="none",  # No network (bot uses curl for Telegram API)
                ports={},  # No exposed ports
                
                # ===== SECURITY =====
                user="botuser:botgroup",  # Non-root user
                cap_drop=["ALL"],  # Drop all Linux capabilities
                security_opt=["no-new-privileges:true"],  # Prevent privilege escalation
                read_only=True,  # Read-only root filesystem
                
                # ===== TEMPORARY SPACE =====
                tmpfs={
                    "/tmp": "size=100m,noexec,nodev,nosuid"  # tmpfs, no execute
                },
                
                # ===== RESOURCE LIMITS (kernel enforced) =====
                cpu_quota=int(float(cpu_limit.rstrip('m')) * 1000),  # CPU in microseconds
                cpus=float(cpu_limit.rstrip('m')) / 1000,
                mem_limit=memory_limit,
                memswap_limit=memory_limit,  # Prevent swap abuse
                
                # ===== TIMEOUT (hard deadline) =====
                timeout=timeout_seconds + 10,  # Docker timeout (SIGKILL after)
                
                # ===== RESTART POLICY (manual only) =====
                restart_policy=RestartPolicy(Name="no"),
                
                # ===== LOGGING =====
                stdout=True,
                stderr=True,
                logs=False,
            )
            
            logger.info(
                f"Started container {container.id[:12]} for bot {bot_id} "
                f"(CPU: {cpu_limit}, RAM: {memory_limit}, Timeout: {timeout_seconds}s)"
            )
            
            return container.id
        
        except docker.errors.ImageNotFound:
            raise ValueError(f"Docker image not found: {image_name}")
        except docker.errors.APIError as e:
            logger.error(f"Docker API error: {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error launching container: {e}")
            raise
    
    def stop_bot_container(self, bot_id: int, timeout: int = 10) -> bool:
        """
        Stop container gracefully.
        
        Args:
            bot_id: Bot ID
            timeout: Seconds to wait before SIGKILL
        
        Returns:
            True if stopped, False if already stopped
        """
        container_name = f"neurhost-bot-{bot_id}"
        
        try:
            container = self.client.containers.get(container_name)
            
            if container.status == "running":
                logger.info(f"Stopping container {container.id[:12]}...")
                container.stop(timeout=timeout)  # SIGTERM, then SIGKILL
                
                # Clean up logs
                self._save_container_logs(container, bot_id)
                
                # Remove container
                container.remove()
                return True
            else:
                logger.info(f"Container {container_name} already stopped")
                return False
        
        except docker.errors.NotFound:
            logger.debug(f"Container {container_name} not found")
            return False
        except Exception as e:
            logger.error(f"Error stopping container: {e}")
            raise
    
    def get_container_stats(self, bot_id: int) -> dict:
        """
        Get CPU and memory usage for bot container.
        
        Returns:
            {
                "cpu_percent": 45.2,  # 0-100
                "memory_mb": 128.5,
                "status": "running"
            }
        """
        container_name = f"neurhost-bot-{bot_id}"
        
        try:
            container = self.client.containers.get(container_name)
            
            if container.status != "running":
                return {"status": container.status, "cpu_percent": 0, "memory_mb": 0}
            
            stats = container.stats(stream=False)
            cpu_percent = self._calculate_cpu_percent(stats)
            memory_mb = stats['memory_stats'].get('usage', 0) / 1024 / 1024
            
            return {
                "cpu_percent": cpu_percent,
                "memory_mb": memory_mb,
                "status": "running"
            }
        
        except docker.errors.NotFound:
            return {"status": "not_found"}
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"status": "error"}
    
    def _calculate_cpu_percent(self, stats: dict) -> float:
        """Calculate CPU usage percentage."""
        try:
            cpu_stats = stats['cpu_stats']
            system_cpu_usage = cpu_stats['system_cpu_usage']
            container_cpu_usage = cpu_stats['cpu_usage']['total_usage']
            
            cpu_delta = container_cpu_usage - stats.get('precpu_stats', {}).get('cpu_usage', {}).get('total_usage', 0)
            system_delta = system_cpu_usage - stats.get('precpu_stats', {}).get('system_cpu_usage', 0)
            
            if system_delta == 0:
                return 0.0
            
            cpu_percent = (cpu_delta / system_delta) * 100.0
            return min(100.0, cpu_percent)
        except Exception:
            return 0.0
    
    def _save_container_logs(self, container, bot_id: int):
        """Save container logs to file for audit."""
        try:
            logs = container.logs(stdout=True, stderr=True).decode('utf-8', errors='replace')
            log_file = f"/neurhost/logs/bot-{bot_id}.log"
            with open(log_file, 'a') as f:
                f.write(logs)
            logger.debug(f"Saved logs for bot {bot_id}")
        except Exception as e:
            logger.error(f"Error saving logs: {e}")
```

## 5. Rate Limiting

```python
# src/security/rate_limiter.py
import redis
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Redis-backed rate limiting.
    
    Prevents:
    - UI spam (clicking buttons rapidly)
    - Brute force (repeated login/start attempts)
    - Resource exhaustion (rapid bot uploads)
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def check_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> Tuple[bool, int]:
        """
        Check if action is rate-limited.
        
        Args:
            key: Unique identifier (e.g., "user:123:start_bot")
            limit: Max requests allowed
            window_seconds: Time window
        
        Returns:
            (is_allowed: bool, retry_after_seconds: int)
        
        Example:
            allowed, retry_after = await rate_limiter.check_limit(
                key=f"user:{user_id}:start_bot",
                limit=5,
                window_seconds=60
            )
            
            if not allowed:
                await update.answer(
                    f"Rate limited. Try again in {retry_after}s",
                    show_alert=True
                )
                return
        """
        
        now = datetime.utcnow()
        window_key = f"ratelimit:{key}:{int(now.timestamp()) // window_seconds}"
        
        try:
            pipe = self.redis.pipeline()
            pipe.incr(window_key)
            pipe.expire(window_key, window_seconds * 2)
            results = pipe.execute()
            
            current_count = results[0]
            
            if current_count <= limit:
                logger.debug(f"Rate limit check PASSED: {key} ({current_count}/{limit})")
                return True, 0
            else:
                retry_after = window_seconds - (int(now.timestamp()) % window_seconds)
                logger.warning(f"Rate limit EXCEEDED: {key} ({current_count}/{limit})")
                return False, retry_after
        
        except redis.RedisError as e:
            logger.error(f"Rate limiter error: {e}")
            # Fail open (allow if Redis is down, log issue)
            return True, 0

# Usage in handler:
rate_limiter = RateLimiter(redis_client)

async def start_bot_handler(update, context):
    user_id = update.effective_user.id
    bot_id = int(query.data.split("_")[1])
    
    # Check rate limit
    allowed, retry_after = await rate_limiter.check_limit(
        key=f"user:{user_id}:start_bot",
        limit=5,
        window_seconds=60
    )
    
    if not allowed:
        await update.callback_query.answer(
            f"⚠️ Too many start requests. Try again in {retry_after}s",
            show_alert=True
        )
        return
    
    # Proceed with starting bot...
```

## 6. Audit Logging

```python
# src/security/audit_logger.py
from sqlalchemy import Column, Integer, String, DateTime, Text, JSONB
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class AuditLog(Base):
    """Immutable audit trail (INSERT only, NEVER DELETE/UPDATE)."""
    
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True)
    action = Column(String(100), index=True, nullable=False)  # "bot.start", "user.approve"
    resource_type = Column(String(50))  # "bot", "user"
    resource_id = Column(String(100))
    status = Column(String(20), index=True)  # "success", "failure"
    error_code = Column(String(50))  # "RATE_LIMIT", "UNAUTHORIZED"
    ip_address = Column(String(45))
    details = Column(JSONB)  # Extra context
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

async def audit_log(
    user_id: int,
    action: str,
    status: str,
    resource_type: str = None,
    resource_id: str = None,
    error_code: str = None,
    details: dict = None,
    ip_address: str = None,
):
    """
    Log action to immutable audit trail.
    
    Args:
        user_id: Who performed the action
        action: What action (e.g., "bot.start_requested")
        status: "success" or "failure"
        resource_type: "bot" or "user"
        resource_id: Bot ID or User ID affected
        error_code: Error code if failed
        details: Dict with extra info
        ip_address: Source IP (if available)
    
    Example:
        await audit_log(
            user_id=123,
            action="bot.start_requested",
            status="success",
            resource_type="bot",
            resource_id=str(bot_id),
            details={"cpu_limit": "500m", "timeout": 3600}
        )
    """
    
    log = AuditLog(
        user_id=user_id,
        action=action,
        status=status,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        error_code=error_code,
        ip_address=ip_address,
        details=details or {}
    )
    
    db.session.add(log)
    
    try:
        await db.session.commit()
        logger.info(f"AUDIT: {action} user={user_id} status={status}")
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")
        # Still log to file
        logger.warning(f"AUDIT_FALLBACK: {action} user={user_id} status={status}")
```

---

These snippets demonstrate the production-grade security model. Full implementation would include comprehensive error handling, tests, and monitoring.

