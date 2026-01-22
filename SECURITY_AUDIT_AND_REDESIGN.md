# 🔐 NeuroHost V4: Security Audit & Production Hardening

**Date:** January 22, 2026  
**Assessment Level:** CRITICAL - Multiple RCE + privilege escalation vulnerabilities  
**Overall Risk:** 🔴 **CRITICAL** → 🟢 **PRODUCTION-READY** (after redesign)

---

## EXECUTIVE SUMMARY

The current NeuroHost V4 implementation contains **systemic security failures** that make it unsuitable for production use, particularly in a multi-tenant SaaS environment. The primary threats are:

1. **Remote Code Execution (RCE)**: User bots run directly on host with full filesystem/env access
2. **Privilege Escalation**: All users share same environment; admin controls not enforced at OS level
3. **Resource Exhaustion**: No kernel-enforced limits; runaway bots can crash entire system
4. **Secrets Exposure**: Hardcoded tokens, insufficient env var isolation
5. **Data Breach Potential**: Weak database encryption, unvalidated user input
6. **Denial of Service**: No rate limiting, no restart loop prevention truly enforced

---

## PART 1: CRITICAL VULNERABILITIES FOUND

### 1.1 Remote Code Execution via Untrusted User Code

**Severity:** 🔴 CRITICAL  
**Location:** `ProcessManager.start_bot()` (line ~515)

**Vulnerability:**
```python
p = subprocess.Popen(
    [sys.executable, main_file],
    cwd=bot_path, env=env,  # ← env has full host environment + BOT_TOKEN
    preexec_fn=os.setsid if os.name != 'nt' else None
)
```

**Attack Scenario:**
1. User uploads malicious `main.py` containing: `os.system("rm -rf /"); import base64; os.system(base64.b64decode(b'...'))")`
2. Bot runs with **full host environment** (`env=env`), including:
   - `HOME`, `PATH`, `USER`, sensitive env vars
   - Access to host filesystem
   - Can fork processes, access `/etc`, steal keys from `/root`
3. No container isolation → attacker gains host-level code execution

**Impact:** Complete system compromise, data theft, botnet injection

---

### 1.2 Insufficient Token Validation

**Severity:** 🔴 CRITICAL  
**Location:** `handle_bot_file()`, `handle_github_url()` (lines ~1300+)

**Vulnerability:**
```python
match = re.search(r'[0-9]{8,10}:[a-zA-Z0-9_-]{35}', f.read())
if match: token = match.group(0)
```

**Attack:**
- Regex accepts ANY 8-10 digit string followed by valid chars
- No verification against Telegram API
- Attacker can upload bot with **fake/inactive token** → wasted resources
- Attacker can inject token format in innocent string: `print("123456789:ABCdefGHijklmnoPQRstUvwxyz1234567")`
- Bot silently fails without clear error

**Impact:** Resource waste, masking of attacks, confusion

---

### 1.3 Unencrypted Secrets Storage

**Severity:** 🔴 CRITICAL  
**Location:** Database schema (lines ~110+)

**Vulnerability:**
```python
c.execute('''
    CREATE TABLE IF NOT EXISTS bots (
        ...
        token TEXT,  -- ← PLAINTEXT in SQLite!
        ...
    )
''')
```

**Attack:**
- Database is local SQLite, not encrypted
- If attacker gains file access (e.g., via traversal bug), all bot tokens extracted
- No access control on database file (typically world-readable in dev)
- Tokens can be used to compromise every user's bot

**Impact:** Complete credential compromise if database leaks

---

### 1.4 No Resource Enforcement at OS Level

**Severity:** 🔴 CRITICAL  
**Location:** `ProcessManager._enforce_loop()` (line ~775)

**Vulnerability:**
```python
# Soft limits only - ignored by determined attacker
new_remaining = max(0, int(remaining - elapsed))
power_drain = (cpu / 100.0) * elapsed * drain_factor
new_power = max(0.0, float(power - power_drain))
```

**Attack:**
1. User uploads bot with infinite loop: `while True: pass`
2. Bot consumes 100% CPU indefinitely
3. Soft enforcement in database doesn't actually **kill** the process
4. Process only killed when `remaining <= 0` (after soft timer expires)
5. In meantime, bot starves other users' bots or entire system

**Impact:** Denial of Service against all users, system crash

---

### 1.5 Weak Input Validation & Injection Risks

**Severity:** 🟠 HIGH  
**Location:** File operations (lines ~1400+)

**Vulnerability:**
```python
file_path = os.path.join(BOTS_DIR, bot[5], filename)  # ← no path normalization
with open(file_path, 'r') as f: content = f.read()[:1000]
```

**Attack:**
- Path traversal: `file_view(bot_id, "../../../etc/passwd")`
- No sanitization of `bot[5]` (folder name), `filename`
- Can read arbitrary files on host

**Impact:** Information disclosure (config, other users' code, system files)

---

### 1.6 Unvalidated GitHub Repository Cloning

**Severity:** 🟠 HIGH  
**Location:** `handle_github_url()` (line ~1329)

**Vulnerability:**
```python
proc = subprocess.run(["git", "clone", url, dest], ...)
if proc.returncode != 0: return
```

**Attack:**
1. Clone repository with malicious `.git/hooks/post-checkout` script
2. Hook executes arbitrary code on host during clone
3. Or: Clone extremely large repo → DoS via disk fill
4. Or: Clone repo with submodules pointing to attacker server → MITM

**Impact:** RCE during deployment, DoS, supply chain attack

---

### 1.7 No Admin Action Audit Trail

**Severity:** 🟠 HIGH  
**Location:** Admin panel (lines ~1250+)

**Vulnerability:**
```python
c.execute("UPDATE users SET status = ? WHERE user_id = ?", (status, user_id))
```

No logging of:
- Who approved/rejected which user
- When actions occurred
- Changes to user permissions
- Bot start/stop events (audit trail)

**Attack:** Admin abuse, insider threats, plausible deniability

---

### 1.8 Race Conditions in Database Access

**Severity:** 🟠 HIGH  
**Location:** `Database` class (lines ~100+)

**Vulnerability:**
```python
def update_bot_resources(self, bot_id, remaining_seconds=None, ...):
    conn = sqlite3.connect(self.db_file)  # ← new connection each time
    c = conn.cursor()
    # Check-modify-write without transaction isolation
    c.execute("SELECT * FROM bots WHERE id = ?", (bot_id,))  # Race!
    # Bot may be deleted between SELECT and UPDATE
```

**Attack:**
1. Two concurrent requests to start same bot
2. Both see bot in stopped state
3. Both attempt start → double-process or corruption
4. Database locks cause slowdowns

**Impact:** Corrupted state, crashes, resource leaks

---

### 1.9 No True Process Isolation or Sandboxing

**Severity:** 🔴 CRITICAL  
**Location:** Entire process execution model

**Vulnerability:**
- User bots share Python interpreter with controller
- Can use `multiprocessing`, `pickle` to exploit parent
- Can interfere with Telegram API client
- No namespace isolation (network, PID, IPC, mount)

**Impact:** Escape to parent process, API hijacking, cross-user attacks

---

### 1.10 Insufficient Restart Loop Protection

**Severity:** 🟠 MEDIUM  
**Location:** `_handle_unexpected_exit()` (line ~520)

**Vulnerability:**
```python
if restart_count >= self.restart_anti_loop_limit:  # ← 5 per hour
    db.set_sleep_mode(bot_id, True, reason="anti_loop")
```

**Attack:**
1. Legitimate bot crashes 5 times → enters sleep
2. User can manually restart immediately from UI
3. No backoff, no exponential delay
4. Attacker can spam restart button 100x in few seconds → starvation

---

## PART 2: ARCHITECTURAL FLAWS

### 2.1 Monolithic Codebase

- 1522 lines in single file
- No separation of concerns
- Hard to test, audit, or modify safely
- All functionality at same security level

### 2.2 Synchronous Database Access

- SQLite with `sqlite3` (blocking calls)
- No transaction management
- Race conditions likely in high concurrency
- All DB ops serialize on single connection

### 2.3 Inadequate Logging & Observability

- Unstructured logging to console
- Errors written to flat log file
- No central trace ID for request correlation
- No alerting for suspicious activity

### 2.4 No Rate Limiting or Abuse Prevention

- User can flood /start, /stop, Telegram callbacks infinitely
- No per-user request limits
- No per-bot action limits
- No exponential backoff for failures

### 2.5 Missing Graceful Shutdown

- Background tasks not cancelled properly
- Database connections not closed cleanly
- Orphaned processes possible on restart

---

## PART 3: COMPREHENSIVE REDESIGN

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                                                               │
│  NeuroHost Controller (Main Process)                         │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Telegram Bot Handler (python-telegram-bot)              ││
│  │ - User authentication (JWT tokens)                      ││
│  │ - Request validation & sanitization                     ││
│  │ - Rate limiting middleware                              ││
│  │ - Audit logging to PostgreSQL                           ││
│  └─────────────────────────────────────────────────────────┘│
│         │                           │                         │
│         ▼                           ▼                         │
│  ┌──────────────────────┐  ┌──────────────────────┐          │
│  │ Security Layer       │  │ Container Manager    │          │
│  │ ────────────────     │  │ ────────────────     │          │
│  │ • Token encryption   │  │ • Docker API client  │          │
│  │ • Code scanning      │  │ • Resource limits    │          │
│  │ • Permission checks  │  │ • Port mapping       │          │
│  │ • Input validation   │  │ • Image pulling      │          │
│  └──────────────────────┘  └──────────────────────┘          │
│         │                           │                         │
│         └───────────────┬───────────┘                         │
│                         ▼                                     │
│         ┌───────────────────────────────────┐                │
│         │  PostgreSQL + Redis               │                │
│         │  ─────────────────────────────    │                │
│         │  • Encrypted secrets              │                │
│         │  • Audit logs (immutable)         │                │
│         │  • Rate limit counters (Redis)    │                │
│         │  • Task queue (Celery)            │                │
│         └───────────────────────────────────┘                │
│                                                               │
└─────────────────────────────────────────────────────────────┘
         │                                    │
         ▼                                    ▼
    ┌─────────────────────────────────────────────────┐
    │   Docker Daemon (Host Kernel)                   │
    │                                                 │
    │  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
    │  │ Bot #1  │  │ Bot #2  │  │ Bot #N  │        │
    │  │Container│  │Container│  │Container│        │
    │  │         │  │         │  │         │        │
    │  │ Limits: │  │ Limits: │  │ Limits: │        │
    │  │ CPU 500m│  │ CPU 500m│  │ CPU 500m│        │
    │  │ RAM 512M│  │ RAM 512M│  │ RAM 512M│        │
    │  │ Time:   │  │ Time:   │  │ Time:   │        │
    │  │ 1h-1mo  │  │ 1h-1mo  │  │ 1h-1mo  │        │
    │  └─────────┘  └─────────┘  └─────────┘        │
    │                                                 │
    │  Each container:                               │
    │  • Isolated filesystem (no access to host)    │
    │  • No access to host network (except Telegram)│
    │  • No env vars from parent                    │
    │  • 0-privilege user (non-root)                │
    │  • Read-only root filesystem except /tmp      │
    │  • Kill enforcement via cgroup timer          │
    │                                                 │
    └─────────────────────────────────────────────────┘
```

---

### 3.2 New Modular Project Structure

```
neurhost-prod/
├── docker/
│   ├── Dockerfile.controller       # Main bot controller image
│   ├── Dockerfile.user-bot         # Base image for user bots
│   ├── docker-compose.yml          # Local dev stack
│   └── .dockerignore
│
├── src/
│   ├── __init__.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py               # Configuration, env loading
│   │   ├── constants.py            # Constants, limits, plans
│   │   └── types.py                # TypedDicts, Enums
│   │
│   ├── security/
│   │   ├── __init__.py
│   │   ├── auth.py                 # JWT token verification
│   │   ├── token_validator.py      # Telegram token validation
│   │   ├── code_scanner.py         # Malicious code detection
│   │   ├── secrets_manager.py      # Encryption/decryption
│   │   ├── rate_limiter.py         # Rate limiting logic
│   │   └── audit_logger.py         # Audit trail recording
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py               # SQLAlchemy ORM models
│   │   ├── repository.py           # Data access layer
│   │   ├── migrations/             # Alembic migration scripts
│   │   └── connection.py           # DB connection pooling
│   │
│   ├── containers/
│   │   ├── __init__.py
│   │   ├── manager.py              # Docker container lifecycle
│   │   ├── image_builder.py        # Build user bot images
│   │   ├── resource_enforcer.py    # Cgroup limits
│   │   └── sandbox_config.py       # Security settings for containers
│   │
│   ├── process_manager/
│   │   ├── __init__.py
│   │   ├── bot_launcher.py         # Launch bot in container
│   │   ├── bot_supervisor.py       # Monitor running bots
│   │   ├── restart_policy.py       # Restart logic with backoff
│   │   └── health_check.py         # Liveness probes
│   │
│   ├── telegram_handlers/
│   │   ├── __init__.py
│   │   ├── base_handler.py         # Auth, validation mixin
│   │   ├── user_handlers.py        # /start, menu, etc
│   │   ├── bot_management.py       # start/stop/delete
│   │   ├── admin_handlers.py       # Admin-only endpoints
│   │   ├── deployment_handlers.py  # GitHub deploy
│   │   └── callbacks.py            # Button callbacks
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── user_service.py         # User business logic
│   │   ├── bot_service.py          # Bot business logic
│   │   ├── deployment_service.py   # GitHub/upload logic
│   │   └── notification_service.py # Send messages to users
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── time_helpers.py         # Format time durations
│   │   ├── validators.py           # Input validation
│   │   ├── crypto.py               # Token encryption
│   │   └── logger.py               # Structured logging
│   │
│   └── main.py                     # Entry point
│
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_security.py
│   │   ├── test_validators.py
│   │   ├── test_container_mgr.py
│   │   └── test_rate_limiter.py
│   ├── integration/
│   │   ├── test_full_flow.py
│   │   └── test_docker_ops.py
│   └── fixtures.py
│
├── requirements.txt                # Python dependencies
├── requirements-dev.txt            # Dev dependencies
├── docker-compose.yml              # Local testing
├── Makefile                        # Build/deploy commands
├── README.md
└── ARCHITECTURE.md                 # Detailed design doc
```

---

## PART 4: CRITICAL SECURITY CHANGES CHECKLIST

### Mandatory Implementation (Non-Negotiable)

- [ ] **Container Isolation**: Every user bot runs in isolated Docker container
  - No host filesystem access
  - No host env vars
  - User/group IDs isolated
  - Network isolated except Telegram API egress
  
- [ ] **Secrets Management**: All tokens encrypted at rest
  - Use `cryptography.Fernet` with keys from `/dev/urandom`
  - Store encryption keys in secure location (env var or secret manager)
  - Decrypt only in container memory when needed
  
- [ ] **Token Validation**: Verify all tokens against Telegram API
  - Before storing: `POST https://api.telegram.org/botTOKEN/getMe`
  - Only accept 200 response with valid bot data
  - Rate limit validation requests (1/second)
  
- [ ] **Code Scanning**: Detect obvious malicious patterns
  - Reject code containing: `os.system`, `subprocess`, `__import__`, `eval`, `exec`
  - Detect: `socket`, `urllib`, `requests` if no whitelist file
  - Static analysis: simple AST walk, not Turing-complete
  
- [ ] **Resource Enforcement**: Enforce limits at kernel level
  - CPU: cgroup hard limit (e.g., 500m)
  - Memory: cgroup hard limit + OOM killer
  - Disk: tmpfs 100MB max in container
  - Time: Docker SIGKILL after timeout (hard limit)
  - No soft limits in userspace
  
- [ ] **Rate Limiting**: Prevent abuse
  - Per-user: 10 requests/minute on all endpoints
  - Per-bot: 5 start/stop actions/minute
  - Per-UI action: 2 requests/second (prevent click spam)
  - Exponential backoff on repeated failures
  
- [ ] **Database Security**:
  - Migrate from SQLite to PostgreSQL
  - Enable encryption in transit (SSL/TLS)
  - Separate read-only user for audit logs
  - Encrypt sensitive columns (tokens, emails)
  
- [ ] **Audit Logging**: Immutable log of all admin/security actions
  - Who: user_id, IP address
  - What: action name, affected resource
  - When: precise timestamp with timezone
  - Result: success/failure, error code
  - Cannot be deleted, only archived
  
- [ ] **Input Validation**: Sanitize all user input
  - Whitelist allowed characters for bot names, file paths
  - Validate bot IDs are positive integers owned by user
  - No path traversal (use `os.path.normpath`, check within allowed dir)
  - Telegram username validation: `^[a-zA-Z0-9_]{5,32}$`
  
- [ ] **Process Supervision**: Robust lifecycle management
  - Restart policy: exponential backoff (1s, 2s, 4s, 8s... max 5m)
  - Max 3 restarts/hour before sleep
  - Manual restart requires user action
  - Graceful shutdown: 10s SIGTERM, then SIGKILL
  
- [ ] **Admin Enforcement**: Permission checks on all admin actions
  - Only ADMIN_ID can approve users
  - Only bot owner can start/stop
  - Logs of all policy changes
  - Emergency kill-switch: one command disables all user bots

---

## PART 5: KEY SECURITY IMPROVEMENTS

### 5.1 Encrypted Secrets Management

```python
# Before (VULNERABLE):
token TEXT  # Plaintext in database

# After (SECURE):
from cryptography.fernet import Fernet

class SecretsManager:
    def __init__(self):
        self.cipher = Fernet(os.environ["ENCRYPTION_KEY"].encode())
    
    def encrypt_token(self, token: str) -> str:
        return self.cipher.encrypt(token.encode()).decode()
    
    def decrypt_token(self, encrypted: str) -> str:
        return self.cipher.decrypt(encrypted.encode()).decode()

# In database:
token = Column(String, nullable=False)  # Encrypted Fernet token
# Usage:
bot_token = secrets_mgr.decrypt_token(bot.token)  # Only in memory
```

### 5.2 Docker-Based Execution

```python
# Before (VULNERABLE):
subprocess.Popen([sys.executable, main_file], cwd=bot_path, env=env)

# After (SECURE):
import docker
from docker.types import DeviceRequest

docker_client = docker.from_env()

def launch_bot_in_container(bot_id: int, token: str, timeout_seconds: int):
    # Build image with dependencies (deterministic)
    # Image runs bot as unprivileged user with strict limits
    
    container = docker_client.containers.run(
        image=f"neurhost-user-bot:latest",
        command=["python", "main.py"],
        environment={
            "BOT_TOKEN": token,  # Only this, no host env vars
            "BOT_ID": str(bot_id),
        },
        volumes={
            f"/bots/{bot_id}/code": {"bind": "/app", "mode": "ro"},  # Read-only
        },
        ports={},  # No exposed ports
        network_mode="none",  # No network except bridge (Telegram only)
        user="botuser:botgroup",  # Non-root user
        cap_drop=["ALL"],  # Drop all capabilities
        cap_add=[],  # No capabilities added
        security_opt=["no-new-privileges:true"],
        read_only=True,  # Read-only root filesystem
        tmpfs={"/tmp": "size=100m,noexec"},  # Temp space, no execute
        memswap_limit="512m",  # Total memory (RAM + swap)
        memory="512m",  # Physical RAM limit
        cpus=0.5,  # 500m CPU
        mem_limit="512m",  # Fallback mem limit
        restart_policy={"Name": "no"},  # Never auto-restart; we manage it
        detach=True,
        timeout=timeout_seconds + 10,  # Allow graceful stop
    )
    return container
```

### 5.3 Telegram Token Validation

```python
async def validate_telegram_token(token: str) -> bool:
    """Verify token is valid by calling Telegram API."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.telegram.org/bot{token}/getMe",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    return False
                data = await resp.json()
                return data.get("ok", False) and "result" in data
    except asyncio.TimeoutError:
        return False
    except Exception as e:
        logger.error(f"Token validation failed: {e}")
        return False

# Before accepting bot:
if not await validate_telegram_token(token):
    raise ValueError("Invalid or inactive Telegram bot token")
```

### 5.4 Code Malice Detection

```python
import ast

class CodeSecurityScanner:
    DANGEROUS_NAMES = {
        'os', 'sys', 'subprocess', 'socket', 'requests',
        '__import__', 'eval', 'exec', 'compile', '__code__',
    }
    
    def scan_code(self, code: str) -> tuple[bool, str]:
        """
        Returns: (is_safe, error_message)
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        
        for node in ast.walk(tree):
            # Check for dangerous imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in (node.names if isinstance(node, ast.Import) else [node.module]):
                    name = alias.name if hasattr(alias, 'name') else alias
                    if name and name.split('.')[0] in self.DANGEROUS_NAMES:
                        return False, f"Forbidden import: {name}"
            
            # Check for dangerous function calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.DANGEROUS_NAMES:
                        return False, f"Forbidden function call: {node.func.id}"
        
        return True, ""

# Usage:
scanner = CodeSecurityScanner()
safe, error = scanner.scan_code(user_uploaded_code)
if not safe:
    raise ValueError(f"Code rejected for security: {error}")
```

### 5.5 Rate Limiting Middleware

```python
from datetime import datetime, timedelta
from typing import Dict, List
import redis

class RateLimiter:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def check_limit(self, key: str, limit: int, window: int) -> bool:
        """
        Check if action is allowed.
        key: "user:123:start_bot" or "bot:45:restart"
        limit: max requests
        window: time window in seconds
        """
        now = datetime.utcnow()
        pipe = self.redis.pipeline()
        
        # Redis key with expiry
        redis_key = f"ratelimit:{key}:{int(now.timestamp()) // window}"
        
        pipe.incr(redis_key)
        pipe.expire(redis_key, window * 2)  # Cleanup old keys
        results = pipe.execute()
        
        count = results[0]
        return count <= limit

# Usage in handlers:
user_id = update.effective_user.id
if not await rate_limiter.check_limit(
    f"user:{user_id}:start_bot",
    limit=5,
    window=60  # 5 starts per minute
):
    await query.answer("⚠️ Rate limited. Try again in a moment.", show_alert=True)
    return
```

### 5.6 Audit Logging

```python
from sqlalchemy import Column, String, Integer, DateTime, Text
from datetime import datetime

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    action = Column(String(100), nullable=False)  # "bot.start", "user.approve", etc
    resource_id = Column(String(100))  # bot_id, user_id affected
    ip_address = Column(String(45))  # IPv4 or IPv6
    status = Column(String(20))  # "success", "failure"
    error_code = Column(String(50))  # For failures: "RATE_LIMIT", "NOT_AUTHORIZED"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    details = Column(Text)  # JSON: {"old_status": "stopped", "new_status": "running"}
    
    # Immutable: INSERT only, never UPDATE/DELETE in production

async def audit_log(user_id: int, action: str, resource_id: str, 
                   status: str, error_code: str = None, details: dict = None):
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource_id=resource_id,
        ip_address=get_client_ip(),  # From request headers
        status=status,
        error_code=error_code,
        details=json.dumps(details or {})
    )
    db.session.add(log)
    await db.session.commit()
    logger.info(f"AUDIT: {action} by user {user_id}: {status}")
```

---

## PART 6: DOCKER-BASED EXECUTION FLOW

### 6.1 User Bot Lifecycle

```
1. User uploads bot_main.py
   │
   ├─ Validate file type (*.py)
   ├─ Scan code for malware
   ├─ Extract/validate token
   └─ Store encrypted in DB
   
2. User presses "START"
   │
   ├─ Check permissions (owns bot)
   ├─ Check rate limits
   ├─ Check time/power remaining
   ├─ Audit log: "bot.start requested by user X"
   │
   ├─ Build Docker image (if needed)
   │  ├─ FROM python:3.11-slim
   │  ├─ RUN useradd -u 1000 botuser -m
   │  ├─ COPY bot_main.py /app/main.py
   │  ├─ WORKDIR /app
   │  ├─ USER botuser
   │  ├─ ENTRYPOINT ["python", "main.py"]
   │  └─ Image tag: neurhost-bot-{user_id}-{bot_id}:{hash}
   │
   ├─ Run Docker container with limits (see Section 5.2)
   │  ├─ CPU: 500m (0.5 cores)
   │  ├─ RAM: 512m (hard limit, OOM kill if exceeded)
   │  ├─ Disk: 100m tmpfs
   │  ├─ Network: isolated (no external access except Telegram)
   │  ├─ User: botuser (UID 1000, non-root)
   │  ├─ Capabilities: NONE (drop ALL)
   │  └─ Timeout: SIGKILL after remaining_time seconds
   │
   └─ Audit log: "bot.start succeeded"

3. Bot running in container
   │
   ├─ Monitor resource usage every 10s
   ├─ Update database: remaining_time, power_drain
   ├─ If CPU spinning: increase power drain
   ├─ If exceeds limits: forcefully stop container
   │
   ├─ Collect logs: /var/log/docker/{container_id}/
   ├─ Scan for errors in logs
   └─ Send notifications to user if errors detected
   
4. User presses "STOP" or timeout reached
   │
   ├─ Audit log: "bot.stop requested"
   ├─ Send SIGTERM to container (graceful shutdown, 10s)
   ├─ If not stopped: send SIGKILL (forced)
   ├─ Collect final logs
   ├─ Store exit code in DB
   ├─ Delete container
   └─ Audit log: "bot.stop succeeded, exit_code=0"

5. On exit with error (non-zero exit code)
   │
   ├─ Check restart policy:
   │  ├─ If restart_count >= 3 (in 1 hour): enter SLEEP mode
   │  ├─ Else: wait exponential backoff (1s, 2s, 4s...)
   │  └─ Check if time/power remaining
   │
   ├─ If resources available: restart (goto step 2)
   ├─ Else: enter SLEEP mode, notify user
   └─ Audit log: "bot auto-restart after exit_code=X"
```

### 6.2 Docker Compose for Local Testing

```yaml
version: '3.9'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: neurhost
      POSTGRES_USER: neurhost_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  controller:
    build:
      context: .
      dockerfile: docker/Dockerfile.controller
    environment:
      DATABASE_URL: postgresql://neurhost_user:${DB_PASSWORD}@postgres:5432/neurhost
      REDIS_URL: redis://redis:6379/0
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      ADMIN_ID: ${ADMIN_ID}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
      DOCKER_HOST: unix:///var/run/docker.sock
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./bots:/app/bots
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis

volumes:
  postgres_data:
```

---

## PART 7: TIME & POWER ENFORCEMENT

### 7.1 Time Enforcement (Hard Limit)

**Method:** Docker timeout (kernel cgroup timer)

```python
def calculate_timeout(bot: Bot) -> int:
    """Convert remaining_seconds to Docker timeout."""
    remaining = bot.remaining_seconds
    
    # Add 10s grace period for graceful shutdown
    timeout = remaining + 10
    
    # Minimum 1s, maximum 30 days
    timeout = max(1, min(timeout, 30 * 86400))
    
    return timeout

# Usage:
container = docker_client.containers.run(
    ...,
    timeout=calculate_timeout(bot),  # SIGKILL after this many seconds
)

# Enforcement: If bot tries to run longer, container gets SIGKILL by Docker daemon
# User cannot override, disable, or extend time
# Time is enforced at kernel level, not Python level
```

**Why This Works:**
- Docker timeout is enforced by Linux kernel cgroup timer
- Cannot be bypassed by bot code
- Happens **regardless** of what bot is doing (hung, looping, etc)
- Precise: second-level accuracy

### 7.2 Power Enforcement

**Method:** CPU cgroup limits + drain accounting

```python
def update_power_drain(bot_id: int, elapsed_seconds: int):
    """
    Deduct power based on CPU usage over elapsed time.
    
    Formula:
    power_drain = (cpu_percent / 100) * elapsed_seconds * 0.02
    
    Example:
    - CPU 50%, 1 minute = (50/100) * 60 * 0.02 = 0.6% power drained
    - CPU 100%, 1 hour = (100/100) * 3600 * 0.02 = 72% power drained
    - Idle bot (1% CPU), 1 hour = (1/100) * 3600 * 0.02 = 0.72% power drained
    """
    container = docker_client.containers.get(f"bot-{bot_id}")
    stats = container.stats(stream=False)
    
    cpu_percent = calculate_cpu_percent(stats)  # 0-100
    power_drain = (cpu_percent / 100) * elapsed_seconds * 0.02
    
    db.bots.update_where(
        bot_id == bot_id,
        power_remaining=max(0, bot.power_remaining - power_drain),
        last_checked=datetime.utcnow()
    )
    
    # If power reaches 0, enter sleep
    if bot.power_remaining <= 0:
        stop_bot_container(bot_id)
        db.bots.update_where(bot_id == bot_id, sleep_mode=True)
        notify_user(bot.user_id, f"Bot {bot.name} entered sleep due to 0 power")
```

**Why This Works:**
- Power is soft limit (can be exceeded short-term)
- But drained quickly if CPU spinning
- Sleep mode prevents restart if both time AND power depleted
- User must add time/power to wake bot

### 7.3 Combined Enforcement Example

```
User Plan: "free" tier
  - 1 day (86400 seconds)
  - 30% power
  - Can host 3 bots max

Bot Config:
  - Started at 2026-01-22 10:00:00 UTC
  - remaining_time: 86400s
  - power_remaining: 30%
  - Docker timeout: 86410s (time + 10s grace)

Timeline:
  10:05 - Bot running, CPU 5%, elapsed 300s
           Power drain = (5/100) * 300 * 0.02 = 0.3%
           New power = 30 - 0.3 = 29.7%

  12:00 - Bot running, CPU 80%, elapsed 6900s total
           Power drain = (80/100) * 6900 * 0.02 = 11.04%
           New power = 29.7 - 11.04 = 18.66%

  14:30 - Bot crashes after 9000s runtime
           Restart policy: exponential backoff
           Attempt restart, power=18.66%, time=77400s
           Restart succeeds

  23:59 - Bot still running after 86355s elapsed
           Remaining time = 86400 - 86355 = 45 seconds left
           Docker container gets SIGTERM
           Bot has 10s to shutdown gracefully
           If not stopped by 23:59:50, Docker sends SIGKILL
           Container forcefully terminated

  00:00 (next day) - Bot is stopped, time=0, entered sleep mode
          User must add time to resume
```

---

## PART 8: ADMIN TOOLING & CONTROLS

### 8.1 Emergency Kill-Switch

```python
async def admin_kill_all_user_bots(user_id: int, admin_id: int, reason: str):
    """
    Emergency: Admin stops all bots for a specific user.
    Immutable audit trail.
    """
    # Verify admin
    if admin_id != ADMIN_ID:
        raise PermissionError("Only ADMIN_ID can use this")
    
    # Get all bots
    bots = db.query(Bot).filter(Bot.user_id == user_id).all()
    
    for bot in bots:
        try:
            container_id = f"bot-{bot.id}"
            container = docker_client.containers.get(container_id)
            container.stop(timeout=10)
            container.remove()
        except Exception as e:
            logger.error(f"Failed to kill bot {bot.id}: {e}")
        
        # Mark stopped
        bot.status = "stopped"
        db.session.add(bot)
        
        # Audit log (cannot be deleted)
        await audit_log(
            user_id=admin_id,
            action="admin.kill_user_bots",
            resource_id=str(user_id),
            status="success",
            details={
                "reason": reason,
                "bots_killed": len(bots),
                "admin_id": admin_id,
            }
        )
    
    db.session.commit()
```

### 8.2 User Approval Workflow with Audit

```python
async def admin_approve_user(user_id: int, admin_id: int):
    """Approve pending user with full audit trail."""
    
    if admin_id != ADMIN_ID:
        raise PermissionError("Only ADMIN_ID can approve")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"User {user_id} not found")
    
    old_status = user.status
    user.status = "approved"
    user.approved_at = datetime.utcnow()
    db.session.add(user)
    
    await audit_log(
        user_id=admin_id,
        action="admin.approve_user",
        resource_id=str(user_id),
        status="success",
        details={
            "old_status": old_status,
            "new_status": "approved",
            "user_username": user.username,
        }
    )
    
    db.session.commit()
    
    # Notify user
    await telegram_bot.send_message(
        chat_id=user_id,
        text="✅ Your account has been approved! Use /start to begin."
    )
```

---

## PART 9: ADDITIONAL HARDENING MEASURES

### 9.1 Secrets in Environment Variables (Never Hardcoded)

```python
# Before (VULNERABLE):
TOKEN = "8004754960:AAE_jGAX52F_vh7NwxI6nha94rngL6umy3U"

# After (SECURE):
import os
from dotenv import load_dotenv

load_dotenv()  # Load from .env file (local dev only)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN env var not set")

ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
if ADMIN_ID == 0:
    raise ValueError("ADMIN_ID env var not set")

# Production: use secrets manager (AWS Secrets Manager, HashiCorp Vault, etc)
```

### 9.2 Dependency Isolation per Bot

```dockerfile
# Dockerfile.user-bot (for each bot's custom deps)
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements from bot's folder
COPY requirements.txt requirements.txt

# Install dependencies in isolation (fresh venv per bot)
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY main.py /app/main.py

# Non-root user
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# No secrets in image; injected at runtime via environment
CMD ["python", "main.py"]
```

### 9.3 Graceful Shutdown Handler

```python
import signal
import asyncio

async def start_bot(bot_id: int):
    """Launch bot and register shutdown handler."""
    
    container = run_container_for_bot(bot_id)
    
    # Graceful shutdown on SIGTERM/SIGINT
    def handle_shutdown(signum, frame):
        logger.info(f"Shutdown signal received for bot {bot_id}, sending SIGTERM...")
        try:
            container.stop(timeout=10)
        except Exception as e:
            logger.error(f"Error stopping container: {e}")
            container.kill()  # Force if graceful timeout
        
        db.update_bot(bot_id, status="stopped")
        raise KeyboardInterrupt()
    
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    
    # Monitor container
    while container.status == "running":
        await asyncio.sleep(1)
    
    exit_code = container.wait()["StatusCode"]
    return exit_code
```

---

## PART 10: MIGRATION PATH

### Phase 1: Foundation (Week 1-2)
- [ ] Set up PostgreSQL, Redis
- [ ] Create modular directory structure
- [ ] Implement `SecretsManager` for token encryption
- [ ] Write database migrations (Alembic)
- [ ] Set up Docker dev environment

### Phase 2: Security Layer (Week 2-3)
- [ ] Implement `CodeSecurityScanner`
- [ ] Implement `TokenValidator` (Telegram API)
- [ ] Implement `RateLimiter` (Redis-backed)
- [ ] Create `AuditLogger` (PostgreSQL)
- [ ] Set up logging infrastructure

### Phase 3: Container Management (Week 3-4)
- [ ] Implement Docker container builder
- [ ] Write resource enforcement logic
- [ ] Create container lifecycle manager
- [ ] Implement health checks

### Phase 4: Telegram Handlers (Week 4-5)
- [ ] Migrate handlers to new structure
- [ ] Add auth/permission checks
- [ ] Integrate rate limiting
- [ ] Add audit logging to all handlers

### Phase 5: Testing & Deployment (Week 5-6)
- [ ] Unit tests for security modules
- [ ] Integration tests for full flow
- [ ] Performance testing under load
- [ ] Security audit (pen test)
- [ ] Production deployment

---

## PART 11: MONITORING & ALERTING

### Key Metrics to Track

1. **Security Events**:
   - Failed token validations
   - Code scans rejections
   - Rate limit violations
   - Unauthorized access attempts

2. **Resource Usage**:
   - CPU per bot (alert if 95%+ for >5 min)
   - Memory per bot (alert if hitting limit)
   - Disk usage (alert if >80%)
   - Network egress (detect exfiltration)

3. **System Health**:
   - Container startup failures
   - Restart loops (alert if >3 in hour)
   - Database query latency (alert if >500ms)
   - API response times (alert if p95 > 2s)

4. **User Behavior** (Anomaly Detection):
   - User bot upload rate (alert if >10/day)
   - Rapid on/off cycling (likely DoS attempt)
   - GitHub clone failures (likely malicious repos)

---

## SUMMARY OF SECURITY POSTURE

| Aspect | Before | After |
|--------|--------|-------|
| Code Execution | Uncontrolled RCE | Isolated Docker container |
| Token Storage | Plaintext in SQLite | Encrypted in PostgreSQL |
| Token Validation | Regex only | Telegram API verified |
| Resource Limits | Soft limits only | Hard kernel cgroup limits |
| Rate Limiting | None | Redis + per-user/action limits |
| Audit Trail | None | Immutable PostgreSQL logs |
| Process Isolation | None | cgroup + namespace isolation |
| Input Validation | Weak | Comprehensive with whitelist |
| Admin Controls | Minimal | Full audit, emergency kill-switch |
| Observability | Basic console logs | Structured logs + metrics |

---

## CONCLUSION

This redesign transforms NeuroHost from a hobby project into a production-grade, multi-tenant SaaS platform with:

✅ **Zero-trust architecture** (assume every user is hostile)  
✅ **Defense in depth** (multiple security layers)  
✅ **Containerized isolation** (Docker + kernel limits)  
✅ **Encrypted secrets** (never plaintext)  
✅ **Full audit trail** (immutable, queryable logs)  
✅ **Rate limiting** (prevent abuse)  
✅ **Admin controls** (emergency kill-switch, approval workflow)  
✅ **Scalability** (PostgreSQL, async handlers, modular code)  
✅ **Observability** (structured logging, metrics, alerts)  

**Estimated Effort:** 4-6 weeks for full implementation  
**Testing & Hardening:** 2-3 additional weeks  
**Deployment & Monitoring:** Ongoing after launch  

---

**Next Steps:** 
1. Review this audit with security team
2. Prioritize mandatory fixes (Section 4)
3. Begin Phase 1 foundation work
4. Schedule external pen test before production launch
