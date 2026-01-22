# NeuroHost V4 - Production-Ready Setup

## Quick Start

### 1. Clone & Setup

```bash
cd /workspaces/Neurhost-bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Generate Encryption Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values:
# - TELEGRAM_BOT_TOKEN
# - ADMIN_ID
# - DATABASE_URL (PostgreSQL)
# - ENCRYPTION_KEY (from step 2)
```

### 4. Database Setup

```bash
# Using docker-compose
docker-compose -f docker/docker-compose.yml up postgres redis -d

# Or with local PostgreSQL
psql -c "CREATE DATABASE neurhost OWNER postgres"
```

### 5. Initialize Database

```bash
python -c "
import asyncio
from src.db.connection import DatabaseConnection
from src.core.config import Config

async def init_db():
    db = DatabaseConnection(Config.DATABASE_URL)
    await db.create_tables()
    await db.close()

asyncio.run(init_db())
"
```

### 6. Run Application

```bash
python -m src.main
```

## Project Structure

```
src/
├── core/              # Configuration & constants
│   ├── config.py
│   └── types.py
├── security/          # Security components
│   ├── secrets_manager.py
│   ├── token_validator.py
│   ├── code_scanner.py
│   ├── rate_limiter.py
│   ├── audit_logger.py
│   ├── permissions.py
│   └── validators.py
├── db/               # Database layer
│   ├── models.py
│   ├── connection.py
│   └── repository.py
├── containers/       # Docker management
│   ├── manager.py
│   └── resource_enforcer.py
├── utils/           # Utilities
│   ├── time_helpers.py
│   └── logger.py
└── main.py          # Entry point
```

## Key Components

### 1. **Secrets Management**
```python
from src.security import SecretsManager

secrets_mgr = SecretsManager(Config.ENCRYPTION_KEY)
encrypted = secrets_mgr.encrypt_token(token)
decrypted = secrets_mgr.decrypt_token(encrypted)
```

### 2. **Token Validation**
```python
from src.security import TelegramTokenValidator

validator = TelegramTokenValidator()
is_valid, error = await validator.validate_token(token)
```

### 3. **Code Scanning**
```python
from src.security import CodeSecurityScanner

scanner = CodeSecurityScanner()
safe, violation = scanner.scan_code(user_code)
```

### 4. **Rate Limiting**
```python
from src.security import RateLimiter

limiter = RateLimiter(redis_client)
allowed, retry_after = await limiter.check_limit(
    key="user:123:action",
    limit=5,
    window_seconds=60
)
```

### 5. **Docker Containers**
```python
from src.containers import DockerContainerManager

docker_mgr = DockerContainerManager()
container_id = docker_mgr.launch_bot_container(
    bot_id=1,
    bot_token=token,
    timeout_seconds=3600
)
```

## Security Checklist

- ✅ Tokens encrypted at rest (Fernet)
- ✅ Code scanned for malware (AST)
- ✅ Tokens validated via Telegram API
- ✅ Rate limiting per user/action
- ✅ All actions audited (immutable logs)
- ✅ Containers isolated (Docker)
- ✅ Resource limits enforced (cgroup)
- ✅ Non-root container user
- ✅ Read-only root filesystem
- ✅ No host environment variables

## Testing

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v --cov=src

# Type checking
mypy src/

# Security scan
bandit -r src/

# Dependency audit
safety check
```

## Deployment

### Docker Compose (Development)

```bash
docker-compose -f docker/docker-compose.yml up
```

### Docker Compose (Production)

```bash
docker-compose -f docker/docker-compose.prod.yml up -d
```

### Kubernetes

```bash
kubectl apply -f k8s/
```

## Monitoring

### Key Metrics

- `security.token.validation.failed` - Invalid tokens attempted
- `security.code_scan.rejected` - Malicious code detected
- `container.cpu.percent` - Bot CPU usage
- `container.memory.percent` - Bot memory usage
- `rate_limit.exceeded` - Rate limit violations

### Logs

All logs are structured JSON for easy parsing:

```bash
# View logs
tail -f /var/log/neurhost/app.log | jq .

# Search for errors
grep '"level":"ERROR"' /var/log/neurhost/app.log | jq .
```

## Troubleshooting

### Docker connection error

```bash
# Check Docker socket
ls -la /var/run/docker.sock

# Test Docker client
python -c "import docker; d = docker.from_env(); print(d.ping())"
```

### Database connection error

```bash
# Check PostgreSQL
psql postgresql://user:pass@localhost:5432/neurhost -c "SELECT 1"

# Verify DATABASE_URL format
echo $DATABASE_URL
```

### Redis connection error

```bash
# Check Redis
redis-cli ping

# Verify REDIS_URL
echo $REDIS_URL
```

## Next Steps

1. Implement Telegram handlers in `src/telegram_handlers/`
2. Add deployment service for GitHub integration
3. Implement bot supervisor for process monitoring
4. Add comprehensive test suite
5. Deploy to production

---

**Status**: Core security and infrastructure ✅ Complete  
**Next Phase**: Telegram handlers and bot lifecycle management
