# Docker Configuration for NeuroHost V4

## 1. Dockerfile for Main Controller

```dockerfile
# docker/Dockerfile.controller
FROM python:3.11-slim

LABEL maintainer="NeuroHost Team"
LABEL description="NeuroHost V4 - Telegram Bot Hosting Controller"

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 neurhost && \
    mkdir -p /app /neurhost/bots /neurhost/logs && \
    chown -R neurhost:neurhost /app /neurhost

WORKDIR /app

# Copy requirements
COPY requirements.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=neurhost:neurhost src/ ./src/
COPY --chown=neurhost:neurhost config/ ./config/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)"

# Run as non-root
USER neurhost

# Default command
CMD ["python", "-m", "src.main"]

# Environment variables (to be set at runtime)
ENV PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO
```

## 2. Dockerfile for User Bot Base Image

```dockerfile
# docker/Dockerfile.user-bot
# This is the base image used for running user bots
# Each user's bot gets a custom image built FROM this

FROM python:3.11-slim

LABEL description="NeuroHost User Bot Runtime"

# Install minimal runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with limited privileges
RUN useradd -m -u 1000 -s /sbin/nologin botuser

# Create app directory
RUN mkdir -p /app && chown -R botuser:botuser /app

WORKDIR /app

# Copy bot code (will be mounted as read-only volume)
# This is a placeholder; actual code comes from volume mount
COPY --chown=botuser:botuser main.py .

# Security: No root privileges
USER botuser

# Set Python to unbuffered mode
ENV PYTHONUNBUFFERED=1

# Entrypoint: run the bot
ENTRYPOINT ["python"]
CMD ["main.py"]

# SECURITY NOTES:
# - Running as non-root user (botuser, UID 1000)
# - No sudo, no shell
# - Read-only root filesystem (enforced at container runtime)
# - Limited capabilities (enforced at runtime)
# - No access to /proc, /sys (enforced at runtime)
```

## 3. Dockerfile for Building User Bot Images

```dockerfile
# docker/Dockerfile.user-bot-builder
# Used to build custom bot images with user-specified dependencies

ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim as builder

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements (passed via build arg)
ARG BOT_ID
COPY bots/${BOT_ID}/requirements.txt /tmp/requirements.txt

# Pre-compile dependencies
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# ===== RUNTIME IMAGE =====
FROM python:${PYTHON_VERSION}-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /sbin/nologin botuser

WORKDIR /app
RUN chown -R botuser:botuser /app

# Copy dependencies from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy bot code (read-only mount)
COPY --chown=botuser:botuser main.py .

USER botuser
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python"]
CMD ["main.py"]
```

## 4. docker-compose.yml for Development

```yaml
# docker/docker-compose.yml
# Full stack for local development and testing

version: '3.9'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    container_name: neurhost-db
    environment:
      POSTGRES_DB: neurhost
      POSTGRES_USER: neurhost_user
      POSTGRES_PASSWORD: ${DB_PASSWORD:-dev_password}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U neurhost_user"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - neurhost-network

  # Redis Cache
  redis:
    image: redis:7-alpine
    container_name: neurhost-cache
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - neurhost-network

  # NeuroHost Controller
  controller:
    build:
      context: ..
      dockerfile: docker/Dockerfile.controller
      args:
        - PYTHON_VERSION=3.11
    container_name: neurhost-controller
    environment:
      # Telegram
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      ADMIN_ID: ${ADMIN_ID:-123456}
      
      # Database
      DATABASE_URL: postgresql://neurhost_user:${DB_PASSWORD:-dev_password}@postgres:5432/neurhost
      DATABASE_SSL_MODE: disable  # Dev only; use require in prod
      
      # Cache
      REDIS_URL: redis://redis:6379/0
      
      # Secrets
      ENCRYPTION_KEY: ${ENCRYPTION_KEY:-dGVzdGtleWJhc2U2NGVuY29kZWQzMmJ5dGVzaGhlcmZvcm5vdw==}
      
      # Logging
      LOG_LEVEL: DEBUG
      LOG_FILE: /neurhost/logs/controller.log
      
      # Docker
      DOCKER_HOST: unix:///var/run/docker.sock
    ports:
      - "8000:8000"
    volumes:
      # Docker socket for container management
      - /var/run/docker.sock:/var/run/docker.sock:ro
      
      # Bot storage
      - ./bots:/neurhost/bots
      
      # Logs
      - ./logs:/neurhost/logs
      
      # Application code (for development)
      - ../src:/app/src:ro
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - neurhost-network
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/health', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local

networks:
  neurhost-network:
    driver: bridge
```

## 5. docker-compose.yml for Production

```yaml
# docker/docker-compose.prod.yml
# Production-grade configuration with security hardening

version: '3.9'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: neurhost
      POSTGRES_USER: neurhost_user
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    secrets:
      - db_password
    restart: always
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U neurhost_user"]
      interval: 30s
      timeout: 10s
      retries: 5
    networks:
      - neurhost-network
    # Resource limits
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    restart: always
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5
    networks:
      - neurhost-network
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 500M

  controller:
    image: neurhost-controller:${VERSION:-latest}
    environment:
      TELEGRAM_BOT_TOKEN_FILE: /run/secrets/telegram_token
      ADMIN_ID_FILE: /run/secrets/admin_id
      DATABASE_URL: postgresql://neurhost_user:${DB_PASSWORD}@postgres:5432/neurhost
      DATABASE_SSL_MODE: require
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      ENCRYPTION_KEY_FILE: /run/secrets/encryption_key
      LOG_LEVEL: INFO
      ENVIRONMENT: production
    secrets:
      - telegram_token
      - admin_id
      - encryption_key
      - db_password
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - neurhost_bots:/neurhost/bots
      - neurhost_logs:/neurhost/logs
    restart: always
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - neurhost-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 60s
      timeout: 10s
      retries: 3
    deploy:
      replicas: 3  # Run 3 instances for redundancy
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
      update_config:
        parallelism: 1
        delay: 10s
        failure_action: rollback

  # Load Balancer (Nginx)
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - controller
    networks:
      - neurhost-network
    restart: always

volumes:
  postgres_data:
  redis_data:
  neurhost_bots:
  neurhost_logs:

networks:
  neurhost-network:
    driver: bridge

secrets:
  telegram_token:
    external: true
  admin_id:
    external: true
  encryption_key:
    external: true
  db_password:
    external: true
```

## 6. Kubernetes Deployment (Alternative to Docker Compose)

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: neurhost-controller
  namespace: neurhost
spec:
  replicas: 3
  selector:
    matchLabels:
      app: neurhost-controller
  template:
    metadata:
      labels:
        app: neurhost-controller
    spec:
      serviceAccountName: neurhost-controller
      
      # Security context
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      
      containers:
      - name: controller
        image: neurhost-controller:latest
        imagePullPolicy: Always
        
        # Environment from secrets
        env:
        - name: TELEGRAM_BOT_TOKEN
          valueFrom:
            secretKeyRef:
              name: neurhost-secrets
              key: telegram_token
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: neurhost-secrets
              key: database_url
        - name: REDIS_URL
          valueFrom:
            configMapKeyRef:
              name: neurhost-config
              key: redis_url
        - name: ENCRYPTION_KEY
          valueFrom:
            secretKeyRef:
              name: neurhost-secrets
              key: encryption_key
        
        # Ports
        ports:
        - containerPort: 8000
          name: http
        
        # Resource limits
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
        
        # Security context
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
            - ALL
        
        # Liveness and readiness probes
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
          failureThreshold: 3
        
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
          failureThreshold: 3
        
        # Volume mounts
        volumeMounts:
        - name: docker-socket
          mountPath: /var/run/docker.sock
          readOnly: true
        - name: bots
          mountPath: /neurhost/bots
        - name: logs
          mountPath: /neurhost/logs
      
      volumes:
      - name: docker-socket
        hostPath:
          path: /var/run/docker.sock
          type: Socket
      - name: bots
        persistentVolumeClaim:
          claimName: neurhost-bots-pvc
      - name: logs
        persistentVolumeClaim:
          claimName: neurhost-logs-pvc

---
apiVersion: v1
kind: Service
metadata:
  name: neurhost-controller
  namespace: neurhost
spec:
  type: LoadBalancer
  selector:
    app: neurhost-controller
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
    name: http
```

## 7. Build Script

```bash
#!/bin/bash
# docker/build.sh
# Build and push Docker images

set -e

VERSION=${1:-latest}
REGISTRY=${2:-docker.io}
IMAGE_PREFIX="neurhost"

echo "🔨 Building NeuroHost Docker images v${VERSION}"

# Build controller image
echo "📦 Building controller image..."
docker build \
  -f docker/Dockerfile.controller \
  -t ${REGISTRY}/${IMAGE_PREFIX}-controller:${VERSION} \
  -t ${REGISTRY}/${IMAGE_PREFIX}-controller:latest \
  .

# Build user bot base image
echo "📦 Building user bot base image..."
docker build \
  -f docker/Dockerfile.user-bot \
  -t ${REGISTRY}/${IMAGE_PREFIX}-user-bot:${VERSION} \
  -t ${REGISTRY}/${IMAGE_PREFIX}-user-bot:latest \
  .

# Push to registry
echo "📤 Pushing images to ${REGISTRY}..."
docker push ${REGISTRY}/${IMAGE_PREFIX}-controller:${VERSION}
docker push ${REGISTRY}/${IMAGE_PREFIX}-controller:latest
docker push ${REGISTRY}/${IMAGE_PREFIX}-user-bot:${VERSION}
docker push ${REGISTRY}/${IMAGE_PREFIX}-user-bot:latest

echo "✅ Build complete!"
```

## 8. Secrets Setup Script

```bash
#!/bin/bash
# docker/setup-secrets.sh
# Create Docker/Kubernetes secrets

set -e

# For Docker Compose
echo "Creating Docker secrets..."

echo "${TELEGRAM_BOT_TOKEN}" | docker secret create telegram_token -
echo "${ADMIN_ID}" | docker secret create admin_id -
echo "${ENCRYPTION_KEY}" | docker secret create encryption_key -
echo "${DB_PASSWORD}" | docker secret create db_password -

# For Kubernetes
echo "Creating Kubernetes secrets..."

kubectl create secret generic neurhost-secrets \
  --from-literal=telegram_token="${TELEGRAM_BOT_TOKEN}" \
  --from-literal=encryption_key="${ENCRYPTION_KEY}" \
  --from-literal=database_url="postgresql://neurhost_user:${DB_PASSWORD}@postgres:5432/neurhost" \
  -n neurhost

echo "✅ Secrets created"
```

## Usage Examples

### Local Development

```bash
# Build and start stack
docker-compose -f docker/docker-compose.yml up --build

# View logs
docker-compose -f docker/docker-compose.yml logs -f controller

# Run shell
docker-compose -f docker/docker-compose.yml exec controller bash
```

### Production Deployment

```bash
# Build images
./docker/build.sh v1.0.0 gcr.io/my-project

# Create secrets
export TELEGRAM_BOT_TOKEN="..."
export ENCRYPTION_KEY="..."
export DB_PASSWORD="..."
./docker/setup-secrets.sh

# Deploy with Docker Swarm
docker stack deploy -c docker/docker-compose.prod.yml neurhost

# Or with Kubernetes
kubectl apply -f k8s/
```

