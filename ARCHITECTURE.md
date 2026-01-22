# NeuroHost V4 Production Architecture

## Table of Contents

1. [System Architecture Diagram](#system-architecture-diagram)
2. [Module Responsibilities](#module-responsibilities)
3. [Data Flow Diagrams](#data-flow-diagrams)
4. [Database Schema (PostgreSQL)](#database-schema)
5. [API & Security Model](#api--security-model)
6. [Deployment Architecture](#deployment-architecture)

---

## System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          NEURHOST PRODUCTION SYSTEM                      │
└──────────────────────────────────────────────────────────────────────────┘

┌─ TELEGRAM API ──────────────────────────────────────────────────────────┐
│                                                                           │
│  Incoming messages/callbacks → Controller receives via Telegram lib     │
│  ← Outgoing messages (status, errors, notifications)                   │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
        ┌────────────────────────────────────────────────────────┐
        │  NeuroHost Controller (Main Application)              │
        │  - Single instance or replicated behind load balancer │
        │  - Python 3.11+ with python-telegram-bot 20+          │
        ├────────────────────────────────────────────────────────┤
        │                                                        │
        │  ┌──────────────────────────────────────────────────┐ │
        │  │ Telegram Handler Layer                           │ │
        │  │ ├─ start_handler()          [Auth mixin]        │ │
        │  │ ├─ button_handler()         [Permission check]  │ │
        │  │ ├─ bot_upload_handler()     [Validation]        │ │
        │  │ ├─ github_deploy_handler()  [Sanitization]      │ │
        │  │ └─ admin_handler()          [Admin-only guard]  │ │
        │  └──────────────────────────────────────────────────┘ │
        │           │                                           │
        │           ▼                                           │
        │  ┌──────────────────────────────────────────────────┐ │
        │  │ Security & Validation Layer                      │ │
        │  │ ├─ RateLimiter (Redis)      [Prevent abuse]     │ │
        │  │ ├─ CodeScanner (AST)        [Malware detect]    │ │
        │  │ ├─ TokenValidator           [Telegram verify]   │ │
        │  │ ├─ InputValidator           [Sanitization]      │ │
        │  │ └─ PermissionChecker        [Auth enforce]      │ │
        │  └──────────────────────────────────────────────────┘ │
        │           │                                           │
        │           ▼                                           │
        │  ┌──────────────────────────────────────────────────┐ │
        │  │ Business Logic Layer (Services)                  │ │
        │  │ ├─ UserService              [User management]    │ │
        │  │ ├─ BotService               [Bot lifecycle]      │ │
        │  │ ├─ DeploymentService        [GitHub/upload]     │ │
        │  │ ├─ ContainerOrchestrator    [Docker API]        │ │
        │  │ └─ NotificationService      [Send messages]     │ │
        │  └──────────────────────────────────────────────────┘ │
        │           │                                           │
        │           ▼                                           │
        │  ┌──────────────────────────────────────────────────┐ │
        │  │ Data Access Layer (Repository Pattern)           │ │
        │  │ ├─ UserRepository           [ORM queries]        │ │
        │  │ ├─ BotRepository                                 │ │
        │  │ ├─ AuditLogRepository       [Read-only]         │ │
        │  │ └─ ResourceRepository       [Resource tracking] │ │
        │  └──────────────────────────────────────────────────┘ │
        │           │                                           │
        └───────────┼───────────────────────────────────────────┘
                    │
        ┌───────────┴──────────────────────────────────────────┐
        │                                                      │
        ▼                                                      ▼
┌────────────────────────┐                        ┌──────────────────────────┐
│   PostgreSQL DB        │                        │  Redis Cache             │
│  ┌──────────────────┐  │                        │  ┌──────────────────┐    │
│  │ users            │  │                        │  │ Rate limit keys  │    │
│  │ bots             │  │                        │  │ Session cache    │    │
│  │ audit_logs       │  │                        │  │ Task queue       │    │
│  │ error_logs       │  │                        │  └──────────────────┘    │
│  │ deployments      │  │                        │                          │
│  │ resource_usage   │  │                        │  Used by:                │
│  └──────────────────┘  │                        │  - RateLimiter           │
│                        │                        │  - Session mgmt          │
│  Backups: Daily        │                        │  - Bot status updates    │
│  Encryption: At rest   │                        │  - Notification queue    │
│  Replication: Standby  │                        │  TTL: Auto-expire old    │
│                        │                        │                          │
└────────────────────────┘                        └──────────────────────────┘
        ▲                                                     ▲
        │ SSL/TLS                                            │ Unix socket
        │                                                    │
        └────────────────────────────────────────────────────┘
                                │
                ┌───────────────┴────────────────────┐
                │                                    │
                ▼                                    ▼
    ┌─────────────────────────┐        ┌──────────────────────────┐
    │  DOCKER DAEMON (Host)   │        │  Container Runtime       │
    │                         │        │  (containerd/runc)       │
    │  ┌─────┬─────┬─────┐   │        │                          │
    │  │Bot │Bot │Bot │   │        │  Enforces:               │
    │  │Ctn │Ctn │Ctn │   │        │  - CPU limits (cgroup)   │
    │  │  1 │  2 │  N │   │        │  - Memory limits         │
    │  └─────┴─────┴─────┘   │        │  - Process limits        │
    │                         │        │  - Network isolation     │
    │  Each container:        │        │  - Mount namespaces      │
    │  • Read-only root FS    │        │  - User namespaces       │
    │  • No host env vars     │        │  - IPC isolation         │
    │  • 512m RAM limit       │        │  - PID namespace         │
    │  • 500m CPU limit       │        │                          │
    │  • 1-30 day timeout     │        │  Kernel enforces:       │
    │  • tmpfs /tmp only      │        │  - Resource exhaustion   │
    │  • No capabilities      │        │  - Privilege escalation  │
    │  • Non-root user        │        │                          │
    │                         │        │  Cannot be bypassed by   │
    └─────────────────────────┘        │  bot code                │
                                        │                          │
                                        └──────────────────────────┘
```

---

## Module Responsibilities

### Core Module

| File | Responsibility |
|------|-----------------|
| `config.py` | Load env vars, validate configuration, define constants |
| `constants.py` | Bot plan limits, resource quotas, error codes, timeouts |
| `types.py` | TypedDicts for User, Bot, AuditLog; Enums for Status |

### Security Module

| File | Responsibility |
|------|-----------------|
| `auth.py` | JWT token generation/verification for API users |
| `token_validator.py` | Verify Telegram bot tokens against Telegram API |
| `code_scanner.py` | AST-based malware detection (forbid dangerous imports) |
| `secrets_manager.py` | Encrypt/decrypt tokens using `cryptography.Fernet` |
| `rate_limiter.py` | Redis-backed rate limiting (per-user, per-action) |
| `audit_logger.py` | Immutable audit trail to PostgreSQL (INSERT only) |

### Database Module

| File | Responsibility |
|------|-----------------|
| `models.py` | SQLAlchemy ORM: User, Bot, AuditLog, ErrorLog, Deployment |
| `repository.py` | Data access layer: queries, transactions, migrations |
| `connection.py` | Connection pooling, async engine setup |
| `migrations/` | Alembic scripts for schema versioning |

### Container Module

| File | Responsibility |
|------|-----------------|
| `manager.py` | Docker client wrapper: run/stop/monitor containers |
| `image_builder.py` | Build user-bot images with dependencies |
| `resource_enforcer.py` | Read cgroup stats, calculate power drain |
| `sandbox_config.py` | Security config: caps, mounts, network mode |

### Process Manager Module

| File | Responsibility |
|------|-----------------|
| `bot_launcher.py` | Launch bot in Docker container with limits |
| `bot_supervisor.py` | Monitor running bots, collect logs, detect errors |
| `restart_policy.py` | Exponential backoff, anti-loop detection, cooldown |
| `health_check.py` | Liveness/readiness probes for containers |

### Telegram Handlers Module

| File | Responsibility |
|------|-----------------|
| `base_handler.py` | Common: auth check, permission verify, rate limit check |
| `user_handlers.py` | /start, /help, main menu, settings |
| `bot_management.py` | Upload, GitHub deploy, start, stop, delete bots |
| `admin_handlers.py` | Approval workflow, user blocking, emergency controls |
| `deployment_handlers.py` | GitHub clone, requirements detection, token scan |
| `callbacks.py` | Button handlers: inline keyboard responses |

### Services Module

| File | Responsibility |
|------|-----------------|
| `user_service.py` | Create user, approve, block, get user data |
| `bot_service.py` | Create bot, update status, compute time/power |
| `deployment_service.py` | Git clone, code validation, image build |
| `notification_service.py` | Send messages to users (async, with retry) |

### Utils Module

| File | Responsibility |
|------|-----------------|
| `time_helpers.py` | Format seconds to "5d 3h 2m 1s" |
| `validators.py` | Whitelist username, bot name, path; no traversal |
| `crypto.py` | Encrypt/decrypt utilities (wrapper around secrets_manager) |
| `logger.py` | Structured logging with JSON output |

---

## Data Flow Diagrams

### 1. Bot Upload & Validation Flow

```
User sends file
      │
      ▼
┌─────────────────────────────────┐
│ handle_bot_file()               │
│ - Download file from Telegram   │
│ - Validate extension (.py only) │
│ - Save to temp location         │
└─────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────┐
│ CodeSecurityScanner.scan()      │
│ - Parse as AST                  │
│ - Check for dangerous imports   │
│ - Check for dangerous calls     │
│ - REJECT if suspicious          │
└─────────────────────────────────┘
      │
      ▼ (if safe)
┌─────────────────────────────────┐
│ Extract token via regex         │
│ Ask user for manual token input │
└─────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────┐
│ TokenValidator.validate()       │
│ - Call Telegram API: getMe()    │
│ - Verify response is valid      │
│ - REJECT if API returns error   │
└─────────────────────────────────┘
      │
      ▼ (if valid)
┌─────────────────────────────────┐
│ SecretsManager.encrypt()        │
│ - Encrypt token with Fernet key │
│ - Store in PostgreSQL (encrypted)
│ - Never store plaintext         │
└─────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────┐
│ BotService.create_bot()         │
│ - Insert into bots table        │
│ - Set plan limits (time/power)  │
│ - Move code to safe directory   │
│ - Audit log: bot.uploaded       │
└─────────────────────────────────┘
      │
      ▼
User sees: ✅ Bot uploaded successfully
```

### 2. Bot Start Flow (with Safeguards)

```
User presses START
      │
      ▼
┌─────────────────────────────────┐
│ Permission check                │
│ - Verify user owns bot          │
│ - NOT: admin check needed       │
│ - REJECT if not owner           │
└─────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────┐
│ RateLimiter.check()             │
│ - Key: "user:123:start_bot"     │
│ - Limit: 5 starts/minute        │
│ - REJECT if exceeded            │
│ - Audit log: rate.limit_hit     │
└─────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────┐
│ Check resources                 │
│ - remaining_time > 0?           │
│ - remaining_power > 0?          │
│ - NOT in sleep mode?            │
│ - REJECT if any false           │
└─────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────┐
│ Audit log: bot.start_requested  │
│ (immutable PostgreSQL INSERT)   │
└─────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────┐
│ BotLauncher.launch_in_docker()  │
│ - Build image if needed         │
│ - Decrypt token (memory only)   │
│ - Run container with limits:    │
│   - CPU: 500m (hard limit)      │
│   - RAM: 512m (hard limit)      │
│   - Timeout: remaining_time+10  │
│   - User: botuser (non-root)    │
│   - No env vars from parent     │
│   - No host network             │
│ - REJECT if Docker error        │
└─────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────┐
│ BotSupervisor.monitor()         │
│ - Log stdout/stderr             │
│ - Detect errors in logs         │
│ - Send error notifications      │
│ - Track CPU/memory usage        │
└─────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────┐
│ ResourceEnforcer.drain_power()  │
│ - Every 10 seconds:             │
│   - Read cgroup CPU stats       │
│   - Calculate: power_drain =    │
│     (cpu% / 100) * elapsed * 0.02
│   - Deduct from power_remaining │
│   - If power <= 0: enter sleep  │
└─────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────┐
│ Docker kernel timer             │
│ - SIGKILL when timeout reached  │
│ - Cannot be overridden by bot   │
│ - Guaranteed hard stop          │
└─────────────────────────────────┘
      │
      ▼
User sees: 🟢 Bot started
           (live CPU/Memory updates)
           (errors as they occur)
```

### 3. Error Handling & Auto-Restart Flow

```
Bot process exits (or SIGKILL timeout)
      │
      ▼
┌─────────────────────────────────┐
│ WatchProcessExit task           │
│ - Collect exit code             │
│ - Read final logs               │
│ - Log error to audit_logs table │
└─────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────┐
│ Check restart eligibility       │
│ - Count restarts in past hour   │
│ - If >= 3: enter SLEEP mode    │
│   (prevent restart loop)        │
│ - If < 3: continue             │
└─────────────────────────────────┘
      │
      ├─ (if max restarts reached)
      │  └─ Set sleep_mode=1
      │     Notify user: "Too many restarts"
      │     Return
      │
      ▼ (if restarts < 3)
┌─────────────────────────────────┐
│ Check cooldown                  │
│ - Wait exponential backoff:     │
│   1s, 2s, 4s, 8s, 16s... max 5m
│ - Do NOT restart if cooldown    │
│   period not elapsed            │
└─────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────┐
│ Check resources                 │
│ - time_remaining > 0?           │
│ - power_remaining > 0?          │
│ - If NO: check for auto-recovery│
└─────────────────────────────────┘
      │
      ├─ (if time/power depleted)
      │  ├─ Can user auto-recover? (once/day)
      │  │  ├─ YES: Grant 1h + 20% power
      │  │  │       Mark auto_recovery_used=1
      │  │  │       Attempt restart
      │  │  │       Notify user
      │  │  └─ NO: Enter sleep, notify user
      │  └─ Return
      │
      ▼ (if resources available)
┌─────────────────────────────────┐
│ Deduct restart cost             │
│ - power: -2% (restart penalty)  │
│ - time: -60s (restart penalty)  │
└─────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────┐
│ Attempt restart (goto START flow)
│ - If succeeds: Notify user      │
│ - If fails: Log error, add delay│
└─────────────────────────────────┘
      │
      ▼
Audit log: bot.auto_restart_attempt
```

---

## Database Schema

### PostgreSQL Tables

```sql
-- Users
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    username VARCHAR(32) UNIQUE,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, approved, blocked
    plan VARCHAR(20) DEFAULT 'free',  -- free, pro, ultra
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    approved_at TIMESTAMP WITH TIME ZONE,
    blocked_reason TEXT,
    last_activity TIMESTAMP WITH TIME ZONE,
    INDEX (status),
    INDEX (plan)
);

-- Bots
CREATE TABLE bots (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'stopped',  -- stopped, running, sleeping
    token_encrypted VARCHAR(1024) NOT NULL,  -- Fernet encrypted token
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Time tracking
    total_seconds BIGINT DEFAULT 0,  -- From plan
    remaining_seconds BIGINT DEFAULT 0,
    start_time TIMESTAMP WITH TIME ZONE,
    
    -- Power tracking
    power_max REAL DEFAULT 100.0,
    power_remaining REAL DEFAULT 100.0,
    
    -- Sleep mode
    sleep_mode BOOLEAN DEFAULT FALSE,
    sleep_reason VARCHAR(100),
    sleep_since TIMESTAMP WITH TIME ZONE,
    
    -- Restart tracking
    restart_count INT DEFAULT 0,
    restart_window_start TIMESTAMP WITH TIME ZONE,
    last_restart_at TIMESTAMP WITH TIME ZONE,
    auto_recovery_used BOOLEAN DEFAULT FALSE,
    
    -- Deployment
    main_file VARCHAR(255) DEFAULT 'main.py',
    folder VARCHAR(255) NOT NULL,  -- Relative path
    
    -- Docker
    container_id VARCHAR(64),
    
    -- Resource accounting
    cpu_usage_percent REAL DEFAULT 0,
    memory_usage_mb REAL DEFAULT 0,
    last_checked TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX (user_id),
    INDEX (status),
    INDEX (sleep_mode),
    INDEX (last_checked)
);

-- Error & Debug Logs
CREATE TABLE error_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    bot_id BIGINT NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    level VARCHAR(20),  -- ERROR, WARNING, INFO
    message TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    INDEX (bot_id),
    INDEX (timestamp)
);

-- Audit Logs (IMMUTABLE - INSERT ONLY, NEVER DELETE/UPDATE)
CREATE TABLE audit_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,  -- "bot.start", "user.approve", "admin.kill"
    resource_type VARCHAR(50),  -- "bot", "user", "system"
    resource_id VARCHAR(100),
    status VARCHAR(20),  -- "success", "failure"
    error_code VARCHAR(50),
    ip_address VARCHAR(45),
    details JSONB,  -- Extra info
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX (user_id),
    INDEX (action),
    INDEX (created_at),
    INDEX (status)
);

-- Deployments (GitHub, upload history)
CREATE TABLE deployments (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    bot_id BIGINT NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    source VARCHAR(50),  -- "github", "upload"
    source_url VARCHAR(512),  -- GitHub URL or original filename
    commit_hash VARCHAR(40),
    status VARCHAR(20),  -- "pending", "building", "ready", "failed"
    error_message TEXT,
    deployed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    INDEX (bot_id),
    INDEX (status)
);

-- Rate Limit Tracking (Redis, but backup in DB)
CREATE TABLE rate_limits (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    action VARCHAR(100) NOT NULL,
    attempt_count INT DEFAULT 1,
    window_start TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (user_id, action)
);
```

---

## API & Security Model

### Authentication

```python
class JWTAuth:
    """JWT token for API access (future: if exposing API)."""
    
    def create_token(self, user_id: int) -> str:
        payload = {
            "sub": str(user_id),
            "exp": datetime.utcnow() + timedelta(hours=24),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    
    def verify_token(self, token: str) -> int:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            return int(payload["sub"])
        except jwt.ExpiredSignatureError:
            raise ValueError("Token expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")
```

### Permission Model

```python
class PermissionChecker:
    """Role-based permission checks."""
    
    @staticmethod
    def can_manage_bot(user_id: int, bot_id: int) -> bool:
        """Check if user owns bot."""
        bot = db.query(Bot).filter(Bot.id == bot_id).first()
        return bot and bot.user_id == user_id
    
    @staticmethod
    def can_approve_user(user_id: int) -> bool:
        """Only ADMIN_ID can approve users."""
        return user_id == ADMIN_ID
    
    @staticmethod
    def can_upload_bot(user_id: int) -> bool:
        """Check user status and bot limit."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user or user.status != "approved":
            return False
        
        plan_limits = {"free": 3, "pro": 10, "ultra": 100}
        bot_count = db.query(Bot).filter(Bot.user_id == user_id).count()
        limit = plan_limits.get(user.plan, 3)
        
        return bot_count < limit
```

### Security Headers (Future: Web API)

```
Content-Security-Policy: default-src 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-XSS-Protection: 1; mode=block
```

---

## Deployment Architecture

### Production Stack

```
┌─ Load Balancer (NGINX) ──────────────────┐
│                                          │
│  - Reverse proxy for HTTPS               │
│  - Rate limit at edge (fail2ban)         │
│  - Geo-blocking (optional)               │
│                                          │
└──────────┬───────────────────────────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌─────────┐   ┌─────────┐
│  App    │   │  App    │  ← Multiple controller instances
│ Instance│   │ Instance│     (Telegram webhooks with shared cache)
│    1    │   │    2    │
└────┬────┘   └────┬────┘
     │             │
     └──────┬──────┘
            │
    ┌───────┴────────┐
    │                │
    ▼                ▼
┌──────────────┐ ┌──────────────┐
│ PostgreSQL   │ │ Redis        │
│ Primary      │ │ (Replica for │
│              │ │  resilience) │
└──────────────┘ └──────────────┘
    ▲                ▲
    │                │
    └──── Backups ───┘
         (Daily)

┌─────────────────────────────────────────┐
│  Docker Daemon (Host Kernel)            │
│  with Docker Swarm or Kubernetes        │
│  for container orchestration            │
│                                         │
│  - Auto-scaling based on metrics        │
│  - Container distribution               │
│  - Health checks & restart              │
└─────────────────────────────────────────┘
```

### Recommended Hosting

1. **Development**: Docker Compose locally
2. **Staging**: Single host with Docker + PostgreSQL
3. **Production**: 
   - Kubernetes cluster (3+ nodes)
   - Managed PostgreSQL (AWS RDS, Google Cloud SQL)
   - Managed Redis (AWS ElastiCache, etc)
   - Container registry (Docker Hub, ECR, etc)
   - Centralized logging (ELK, Datadog, CloudWatch)

---

## Configuration Management

### Environment Variables (Production)

```bash
# Telegram
export TELEGRAM_BOT_TOKEN="<secret>"
export ADMIN_ID="<admin_user_id>"

# Database
export DATABASE_URL="postgresql://user:pass@host:5432/neurhost"
export DATABASE_SSL_MODE="require"

# Cache
export REDIS_URL="redis://user:pass@host:6379/0"

# Secrets
export ENCRYPTION_KEY="<base64-encoded-32-byte-key>"

# Logging
export LOG_LEVEL="INFO"
export LOG_FILE="/var/log/neurhost/app.log"

# Docker
export DOCKER_HOST="unix:///var/run/docker.sock"

# Features
export ENABLE_GITHUB_DEPLOY="true"
export ENABLE_USER_BOT_UPLOAD="true"
export RATE_LIMIT_ENABLED="true"
```

### Docker Environment Secrets

```yaml
# docker-compose.yml (production)
version: '3.9'
services:
  app:
    environment:
      TELEGRAM_BOT_TOKEN_FILE: /run/secrets/telegram_token
      ENCRYPTION_KEY_FILE: /run/secrets/encryption_key
      DATABASE_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - telegram_token
      - encryption_key
      - db_password

secrets:
  telegram_token:
    external: true  # Managed by orchestrator
  encryption_key:
    external: true
  db_password:
    external: true
```

---

This comprehensive architecture ensures:

✅ Modular, testable code  
✅ Strong security boundaries  
✅ Clear data flow  
✅ Scalability  
✅ Operational safety  

