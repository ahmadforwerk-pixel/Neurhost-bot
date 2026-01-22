# NeuroHost V4: Implementation & Deployment Guide

## Quick Start

### 📋 What You Have

This deliverable includes:

1. **SECURITY_AUDIT_AND_REDESIGN.md** (This Document)
   - Comprehensive security audit of current code
   - 10 critical vulnerabilities identified
   - Detailed fixes for each issue
   - Production-ready architecture

2. **ARCHITECTURE.md**
   - High-level system design
   - Module responsibilities matrix
   - Data flow diagrams
   - Database schema (PostgreSQL)
   - Deployment architecture

3. **CODE_SNIPPETS.md**
   - Production-grade code examples:
     - Token encryption (Fernet)
     - Token validation (Telegram API)
     - Code malware scanning (AST)
     - Docker container manager
     - Rate limiting (Redis)
     - Audit logging

4. **DOCKER_SETUP.md**
   - Dockerfiles for controller and user bots
   - docker-compose.yml for dev and prod
   - Kubernetes manifests
   - Build and deployment scripts

5. **IMPLEMENTATION_GUIDE.md** (This File)
   - Step-by-step implementation roadmap
   - Phase-by-phase breakdown
   - Risk mitigation strategies
   - Testing approach

---

## 🚀 Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
**Goal:** Set up infrastructure and core security components

#### Tasks

1. **Setup PostgreSQL + Redis**
   ```bash
   # Docker Compose (dev)
   docker-compose -f docker/docker-compose.yml up postgres redis
   
   # Or managed services (prod)
   # AWS RDS for PostgreSQL, ElastiCache for Redis
   ```

2. **Create modular project structure**
   ```bash
   mkdir -p src/{core,security,db,containers,process_manager,telegram_handlers,services,utils}
   touch src/{core,security,db,containers,process_manager,telegram_handlers,services,utils}/__init__.py
   ```

3. **Implement configuration layer**
   - `src/core/config.py` - Load env vars with validation
   - `src/core/constants.py` - Plan limits, error codes
   - `src/core/types.py` - TypedDicts for type safety

4. **Setup async database layer**
   - `src/db/models.py` - SQLAlchemy ORM models
   - `src/db/connection.py` - Async connection pooling
   - `src/db/migrations/` - Alembic setup

   ```python
   # Example: src/db/models.py
   from sqlalchemy.ext.asyncio import AsyncSession
   from sqlalchemy.orm import declarative_base, Mapped
   from sqlalchemy import Column, String, Integer, Boolean
   
   Base = declarative_base()
   
   class User(Base):
       __tablename__ = "users"
       
       id: Mapped[int] = Column(Integer, primary_key=True)
       username: Mapped[str] = Column(String(32), unique=True)
       status: Mapped[str] = Column(String(20), default='pending')
       plan: Mapped[str] = Column(String(20), default='free')
   
   class Bot(Base):
       __tablename__ = "bots"
       
       id: Mapped[int] = Column(Integer, primary_key=True)
       user_id: Mapped[int] = Column(Integer, ForeignKey("users.id"))
       token_encrypted: Mapped[str] = Column(String(1024))
       status: Mapped[str] = Column(String(20), default='stopped')
       remaining_seconds: Mapped[int] = Column(Integer, default=0)
       power_remaining: Mapped[float] = Column(Float, default=100.0)
   ```

5. **Implement secrets manager** (See CODE_SNIPPETS.md)
   - `src/security/secrets_manager.py` - Fernet encryption
   - Generate encryption key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   - Store in `.env`: `ENCRYPTION_KEY=<generated-key>`

6. **Create Docker infrastructure**
   - Copy `docker/` folder from DOCKER_SETUP.md
   - Test locally: `docker-compose up`

**Completion Criteria:**
- ✅ PostgreSQL running with schema
- ✅ Redis running and responsive
- ✅ Modular folder structure in place
- ✅ Database connections pooled and async
- ✅ Secrets manager encrypts/decrypts tokens
- ✅ Docker build successful

---

### Phase 2: Security Layer (Week 2-3)
**Goal:** Implement all security checks and validations

#### Tasks

1. **Implement Token Validation** (See CODE_SNIPPETS.md)
   ```python
   # src/security/token_validator.py
   class TelegramTokenValidator:
       async def validate_token(self, token: str) -> Tuple[bool, str]:
           # Call Telegram API: https://api.telegram.org/bot{token}/getMe
           # Verify response is valid
           # Return (is_valid, error_message)
   ```
   
   Test:
   ```bash
   # Unit test
   pytest tests/unit/test_security.py::test_token_validator
   ```

2. **Implement Code Scanner** (See CODE_SNIPPETS.md)
   ```python
   # src/security/code_scanner.py
   class CodeSecurityScanner:
       def scan_code(self, code: str) -> Tuple[bool, str]:
           # Parse as AST
           # Check for dangerous imports: os, sys, subprocess
           # Check for dangerous calls: eval, exec, __import__
           # Return (is_safe, violation_message)
   ```
   
   Test:
   ```python
   # Test malicious code rejection
   malicious = "import os; os.system('rm -rf /')"
   safe, msg = scanner.scan_code(malicious)
   assert not safe
   assert "os.system" in msg
   ```

3. **Implement Rate Limiter** (See CODE_SNIPPETS.md)
   ```python
   # src/security/rate_limiter.py
   class RateLimiter:
       async def check_limit(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
           # Redis-backed rate limiting
           # Return (is_allowed, retry_after_seconds)
   ```

4. **Implement Audit Logger** (See CODE_SNIPPETS.md)
   ```python
   # src/security/audit_logger.py
   async def audit_log(user_id: int, action: str, status: str, ...):
       # INSERT into immutable audit_logs table
       # NEVER allow DELETE/UPDATE on this table
   ```

5. **Implement Permission Checker**
   ```python
   # src/security/permissions.py
   class PermissionChecker:
       @staticmethod
       def can_manage_bot(user_id: int, bot_id: int) -> bool:
           # Check user owns bot
       
       @staticmethod
       def can_approve_user(user_id: int) -> bool:
           # Only ADMIN_ID
   ```

**Completion Criteria:**
- ✅ Token validation via Telegram API
- ✅ Code scanning rejects dangerous imports/calls
- ✅ Rate limiting works with Redis
- ✅ All actions logged to audit_logs
- ✅ Permission checks on all endpoints
- ✅ Unit test coverage >80%

---

### Phase 3: Container Management (Week 3-4)
**Goal:** Implement Docker-based bot execution

#### Tasks

1. **Implement Container Manager** (See CODE_SNIPPETS.md)
   ```python
   # src/containers/manager.py
   class DockerContainerManager:
       def launch_bot_container(
           self, bot_id: int, bot_token: str, 
           timeout_seconds: int, ...
       ) -> str:
           # Run container with strict security settings
           # Return container ID
       
       def stop_bot_container(self, bot_id: int) -> bool:
           # Graceful stop, then force kill
       
       def get_container_stats(self, bot_id: int) -> dict:
           # Return CPU%, memory, status
   ```

2. **Implement Resource Enforcer**
   ```python
   # src/containers/resource_enforcer.py
   class ResourceEnforcer:
       async def update_power_drain(self, bot_id: int):
           # Every 10 seconds:
           # - Read container CPU usage
           # - Calculate power_drain = (cpu% / 100) * elapsed * 0.02
           # - Deduct from power_remaining
           # - If power <= 0: enter sleep mode
   ```

3. **Build user bot base images**
   ```bash
   docker build -f docker/Dockerfile.user-bot \
     -t neurhost-user-bot:latest .
   ```

4. **Implement health checks**
   ```python
   # src/containers/health_check.py
   async def check_bot_health(bot_id: int) -> bool:
       # Check if container is running
       # Check if bot is responsive
   ```

**Completion Criteria:**
- ✅ Container launches with all security settings
- ✅ CPU/RAM limits enforced (cgroup)
- ✅ Containers run as non-root user
- ✅ Power drain calculated and deducted
- ✅ Timeout enforced (SIGKILL at deadline)
- ✅ Integration tests pass

---

### Phase 4: Telegram Handlers (Week 4-5)
**Goal:** Migrate handlers to new modular structure with security

#### Tasks

1. **Create base handler with security mixin**
   ```python
   # src/telegram_handlers/base_handler.py
   class BaseHandler:
       async def check_auth(self, user_id: int) -> bool:
           # Verify user is approved
       
       async def check_permission(self, user_id: int, resource_id: int) -> bool:
           # Verify user owns resource
       
       async def check_rate_limit(self, key: str, limit: int) -> bool:
           # Check rate limiter
       
       async def require_admin(self, user_id: int) -> bool:
           # Only ADMIN_ID
   ```

2. **Implement user handlers**
   ```python
   # src/telegram_handlers/user_handlers.py
   async def start_handler(update, context):
       user_id = update.effective_user.id
       
       # 1. Check auth
       if not await handler.check_auth(user_id):
           return
       
       # 2. Check rate limit
       allowed, retry_after = await rate_limiter.check_limit(
           f"user:{user_id}:start",
           limit=10,
           window_seconds=60
       )
       if not allowed:
           await update.message.reply_text(f"Rate limited, retry in {retry_after}s")
           return
       
       # 3. Send menu
       await send_main_menu(update, context)
       
       # 4. Audit log
       await audit_log(user_id, "user.start", "success")
   ```

3. **Implement bot management handlers**
   ```python
   # src/telegram_handlers/bot_management.py
   async def start_bot_handler(update, context):
       query = update.callback_query
       user_id = update.effective_user.id
       bot_id = int(query.data.split("_")[1])
       
       # 1. Check owns bot
       if not await permiss.can_manage_bot(user_id, bot_id):
           await query.answer("Not authorized", show_alert=True)
           await audit_log(user_id, "bot.start_denied", "failure", 
                          error_code="UNAUTHORIZED")
           return
       
       # 2. Check rate limit
       allowed, _ = await rate_limiter.check_limit(
           f"user:{user_id}:start_bot",
           limit=5,
           window_seconds=60
       )
       if not allowed:
           await audit_log(user_id, "bot.start_denied", "failure",
                          error_code="RATE_LIMIT")
           return
       
       # 3. Check resources
       bot = await db.get_bot(bot_id)
       if bot.remaining_seconds <= 0 or bot.power_remaining <= 0:
           await query.message.reply_text("❌ Insufficient time or power")
           await audit_log(user_id, "bot.start_denied", "failure",
                          error_code="INSUFFICIENT_RESOURCES")
           return
       
       # 4. Start bot
       try:
           container_id = await container_mgr.launch_bot_container(
               bot_id, 
               secrets_mgr.decrypt_token(bot.token_encrypted),
               int(bot.remaining_seconds)
           )
           await db.update_bot_status(bot_id, "running", container_id)
           await query.message.reply_text("✅ Bot started")
           await audit_log(user_id, "bot.start_succeeded", "success",
                          resource_id=str(bot_id))
       except Exception as e:
           await query.message.reply_text(f"❌ Failed: {str(e)[:100]}")
           await audit_log(user_id, "bot.start_failed", "failure",
                          resource_id=str(bot_id),
                          error_code="LAUNCH_ERROR")
   ```

4. **Implement admin handlers**
   ```python
   # src/telegram_handlers/admin_handlers.py
   async def approve_user_handler(update, context):
       query = update.callback_query
       admin_id = update.effective_user.id
       
       if not await permiss.can_approve_user(admin_id):
           await query.answer("Not admin", show_alert=True)
           return
       
       user_id = int(query.data.split("_")[1])
       
       # Approve user
       await db.update_user_status(user_id, "approved")
       
       # Immutable audit log
       await audit_log(admin_id, "user.approve_request", "success",
                      resource_id=str(user_id))
       
       # Notify user
       await context.bot.send_message(user_id, "✅ Approved!")
   ```

5. **Implement deployment handlers**
   ```python
   # src/telegram_handlers/deployment_handlers.py
   async def upload_bot_handler(update, context):
       user_id = update.effective_user.id
       file = update.message.document
       
       # 1. Check rate limit
       allowed, _ = await rate_limiter.check_limit(
           f"user:{user_id}:upload_bot",
           limit=10,
           window_seconds=3600
       )
       if not allowed:
           await update.message.reply_text("Rate limited")
           return
       
       # 2. Download file
       file_obj = await context.bot.get_file(file.file_id)
       code = await file_obj.download_as_bytearray()
       
       # 3. Scan code
       safe, violation = code_scanner.scan_code(code.decode())
       if not safe:
           await update.message.reply_text(f"❌ Code rejected: {violation}")
           await audit_log(user_id, "bot.upload_rejected", "failure",
                          error_code="MALICIOUS_CODE")
           return
       
       # 4. Extract token
       token = extract_token_from_code(code)
       if not token:
           await update.message.reply_text("❌ No token found")
           await audit_log(user_id, "bot.upload_rejected", "failure",
                          error_code="NO_TOKEN")
           return
       
       # 5. Validate token
       is_valid, error = await token_validator.validate_token(token)
       if not is_valid:
           await update.message.reply_text(f"❌ Invalid token: {error}")
           await audit_log(user_id, "bot.upload_rejected", "failure",
                          error_code="INVALID_TOKEN")
           return
       
       # 6. Encrypt and store
       encrypted_token = secrets_mgr.encrypt_token(token)
       bot_id = await db.add_bot(user_id, encrypted_token, file.file_name, ...)
       
       await update.message.reply_text(f"✅ Bot uploaded! ID: {bot_id}")
       await audit_log(user_id, "bot.upload_succeeded", "success",
                      resource_id=str(bot_id))
   ```

**Completion Criteria:**
- ✅ All handlers refactored to use base handler
- ✅ Rate limiting on all endpoints
- ✅ Permission checks on bot management
- ✅ Admin-only actions guarded
- ✅ All actions logged
- ✅ No hardcoded secrets
- ✅ Integration tests pass

---

### Phase 5: Testing & Hardening (Week 5-6)
**Goal:** Comprehensive testing and security validation

#### Tasks

1. **Unit tests** (>80% coverage)
   ```bash
   pytest tests/unit/
   ```

2. **Integration tests**
   ```bash
   pytest tests/integration/
   ```

3. **Security tests**
   ```python
   # tests/security/test_rce_prevention.py
   async def test_cannot_execute_os_system():
       """Bot code with os.system should be rejected."""
       malicious = "import os; os.system('whoami')"
       safe, _ = code_scanner.scan_code(malicious)
       assert not safe
   
   async def test_container_isolation():
       """Bot cannot read host files."""
       # Run container and verify it cannot read /etc/passwd
       result = subprocess.run(
           ["cat", "/etc/passwd"],
           cwd="/neurhost/bots/test-bot",
           capture_output=True
       )
       assert result.returncode != 0
   ```

4. **Load tests**
   ```bash
   locust -f tests/load/locustfile.py -u 100 -r 10 -t 5m
   ```

5. **Penetration testing**
   - Try path traversal in file endpoints
   - Try SQL injection in queries
   - Try token bypass attacks
   - Try privilege escalation

6. **Security audit checklist**
   - [ ] No hardcoded secrets
   - [ ] All user input validated
   - [ ] No SQL injection vectors
   - [ ] No path traversal
   - [ ] Tokens encrypted at rest
   - [ ] All actions logged
   - [ ] Rate limiting works
   - [ ] Containers isolated
   - [ ] Resource limits enforced
   - [ ] Graceful error handling

**Completion Criteria:**
- ✅ >80% code coverage
- ✅ All integration tests pass
- ✅ Security tests pass
- ✅ Load tests stable (p95 <200ms)
- ✅ No vulnerabilities in OWASP Top 10
- ✅ Ready for production

---

## 🔐 Critical Security Checklist

Before launching to production, verify:

### Mandatory Controls

- [ ] **No RCE**
  - User bots run in Docker containers only
  - No host filesystem access
  - No host environment variables
  - Container runs as non-root user
  - Read-only root filesystem (except /tmp)

- [ ] **No Privilege Escalation**
  - No capabilities granted
  - seccomp filter enabled
  - AppArmor/SELinux profile applied

- [ ] **Secrets Protected**
  - No plaintext tokens in code
  - All tokens encrypted with Fernet
  - Encryption key in environment only
  - Key rotated quarterly

- [ ] **Resource Limits Enforced**
  - CPU: 500m cgroup limit (hard)
  - Memory: 512m cgroup limit (hard)
  - Time: Docker timeout (hard, cannot bypass)
  - Disk: 100m tmpfs (hard)

- [ ] **Rate Limiting**
  - Per-user: 10 req/min
  - Per-bot: 5 start/stop per min
  - Per-action: exponential backoff on failures

- [ ] **Audit Trail**
  - All admin actions logged
  - All bot lifecycle events logged
  - All user actions logged
  - Logs immutable (INSERT only)

- [ ] **Input Validation**
  - Whitelist allowed characters
  - Reject path traversal attempts
  - Validate all Telegram IDs are integers
  - Validate bot names, no special chars

- [ ] **Error Handling**
  - No stack traces in responses
  - No sensitive data in error messages
  - Errors logged server-side
  - User sees generic "Error occurred"

- [ ] **Authentication**
  - Only approved users can access
  - Admin-only endpoints protected
  - Permission checks on all resources

### Testing Requirements

- [ ] Penetration testing completed
- [ ] OWASP Top 10 reviewed
- [ ] Code security scan (Bandit) passed
- [ ] Dependency audit (Safety) passed
- [ ] No hardcoded secrets detected

---

## 📊 Monitoring & Alerting

### Key Metrics

```python
# Set up monitoring for:

# Security Events
- "security.token.validation.failed" (alert if >10/hour)
- "security.code_scan.rejected" (alert if >5/hour)
- "security.rate_limit.exceeded" (normal, log only)
- "security.unauthorized_access" (alert immediately)

# Resource Usage
- "container.cpu.percent" (alert if >95% for >5m)
- "container.memory.percent" (alert if >90%)
- "container.timeout.killed" (log, check for issues)

# System Health
- "bot.launch.failed" (alert if >10/hour)
- "database.query.latency_ms" (alert if p95 > 500)
- "api.response.time_ms" (alert if p95 > 2000)

# User Behavior
- "user.bot_upload.rate" (alert if >20/day)
- "user.rapid_restart.attempts" (alert immediately)
- "user.github_clone.failures" (log, track trends)
```

### Alerting Rules

```yaml
# Prometheus rules (example)
alert: UnauthorizedAccessAttempt
expr: rate(security_unauthorized_access_total[5m]) > 0
for: 1m
annotations:
  summary: "Unauthorized access attempt detected"
  action: "Block user, review logs"

alert: HighCPUUsage
expr: container_cpu_percent > 95
for: 5m
annotations:
  summary: "Bot using excessive CPU"
  action: "Check bot code, consider killing if runaway"

alert: RateLimitBypass
expr: rate_limit_bypass_attempts_total > 0
for: 1m
annotations:
  summary: "Rate limit bypass detected"
  action: "Block IP, review attempt"
```

---

## 🚀 Deployment Checklist

### Pre-Deployment

- [ ] All tests passing (unit, integration, security)
- [ ] Load tests show stable performance
- [ ] Database migrations tested on staging
- [ ] Backups configured and tested
- [ ] Rollback plan documented
- [ ] Incident response plan reviewed

### Deployment

- [ ] Blue-green deployment strategy in place
- [ ] Monitoring and alerting enabled
- [ ] Log aggregation (ELK/Datadog) configured
- [ ] On-call rotation established
- [ ] Runbooks written for common issues

### Post-Deployment

- [ ] Monitor for 24 hours continuously
- [ ] Check error rates, latency, resource usage
- [ ] Verify audit logs are being recorded
- [ ] Validate backups are working
- [ ] Document any issues encountered

---

## 📚 References & Resources

### Security Standards
- **OWASP Top 10**: https://owasp.org/www-project-top-ten/
- **CWE Top 25**: https://cwe.mitre.org/top25/
- **NIST Cybersecurity Framework**: https://www.nist.gov/cyberframework

### Docker Security
- **Docker Security Best Practices**: https://docs.docker.com/engine/security/
- **CIS Docker Benchmark**: https://www.cisecurity.org/benchmark/docker/

### Python Security
- **Bandit**: https://bandit.readthedocs.io/ (static analysis)
- **Safety**: https://github.com/pyupio/safety (dependency audit)
- **OWASP Secure Coding**: https://owasp.org/www-community/attacks/

---

## 🆘 Support & Escalation

### If Implementation Gets Stuck

1. **Token Encryption Issues**
   - Verify `ENCRYPTION_KEY` is base64-encoded 32 bytes
   - Test locally: `python -c "from cryptography.fernet import Fernet; Fernet(key.encode())"`

2. **Docker Container Won't Start**
   - Check Docker daemon is running: `docker ps`
   - Verify image exists: `docker images | grep neurhost`
   - Check logs: `docker logs <container_id>`

3. **Database Connection Issues**
   - Verify PostgreSQL is running: `psql -c "SELECT 1"`
   - Check credentials: `echo $DATABASE_URL`
   - Test async connection: `python -c "import asyncio; asyncio.run(engine.connect())"`

4. **Rate Limiting Not Working**
   - Verify Redis is running: `redis-cli ping`
   - Check Redis key TTL: `redis-cli TTL ratelimit:user:123:*`
   - Verify rate limiter implementation calls Redis

### Escalation Path

1. **Tier 1**: Refer to this guide and CODE_SNIPPETS.md
2. **Tier 2**: Review ARCHITECTURE.md and SECURITY_AUDIT_AND_REDESIGN.md
3. **Tier 3**: Engage security team for penetration testing
4. **Tier 4**: Consider external security audit (e.g., Trail of Bits, Bishop Fox)

---

## Final Notes

**This redesign represents a shift from hobbyist to production-grade SaaS architecture.**

The current V4 code was functional but unsafe. This comprehensive redesign addresses:

✅ **10 critical vulnerabilities** (RCE, token exposure, no isolation)  
✅ **Architectural flaws** (monolithic, sync DB, no rate limiting)  
✅ **Operational gaps** (no audit logging, no graceful shutdown, no monitoring)  

Implementation will take **4-6 weeks** for a skilled team, **2-3 additional weeks** for testing and hardening.

The payoff: **A production-ready SaaS platform** that can safely host untrusted user code for thousands of users.

---

**Good luck with the implementation! This is a solid foundation for a real product.**

