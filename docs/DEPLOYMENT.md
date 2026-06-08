# EPMSSTS Deployment Guide

This guide covers deploying EPMSSTS in production environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Docker Deployment](#docker-deployment)
- [Manual Deployment](#manual-deployment)
- [Cloud Deployment](#cloud-deployment)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Hardware Requirements

**Minimum (CPU-only)**:
- 4 CPU cores
- 8GB RAM
- 20GB disk space

**Recommended (with GPU)**:
- 8 CPU cores
- 16GB RAM
- NVIDIA GPU with 8GB+ VRAM
- 50GB disk space

### Software Requirements

- Docker 20.10+
- Docker Compose 2.0+
- PostgreSQL 15+ (if not using Docker)
- Redis 7+ (if not using Docker)

## Docker Deployment

### Quick Start

1. **Clone and configure**
   ```bash
   git clone <repository-url>
   cd EPMSSTS
   cp .env.example .env
   # Edit .env as needed
   ```

2. **Start services**
   ```bash
   docker-compose up -d
   ```

3. **Verify deployment**
   ```bash
   curl http://localhost:8000/health
   ```

4. **View logs**
   ```bash
   docker-compose logs -f api
   ```

### Production Configuration

Edit `docker-compose.yml` for production:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '8'
          memory: 16G
        reservations:
          cpus: '4'
          memory: 8G
    environment:
      LOG_LEVEL: WARNING
      DATABASE_URL: postgresql://user:pass@prod-db:5432/epmssts
      REDIS_URL: redis://prod-redis:6379
```

### GPU Support

For GPU support, update `docker-compose.yml`:

```yaml
services:
  api:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

## Manual Deployment

### 1. System Setup

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y python3.10 python3.10-venv postgresql redis-server ffmpeg libsndfile1

# Create application user
sudo useradd -m -s /bin/bash epmssts
sudo su - epmssts
```

### 2. Application Setup

```bash
# Clone repository
git clone <repository-url>
cd EPMSSTS

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Database Setup

```bash
# Create database
sudo -u postgres psql
CREATE DATABASE epmssts;
CREATE USER epmssts WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE epmssts TO epmssts;
\q

# Initialize schema
psql -U epmssts -d epmssts -f epmssts/services/database/schema.sql
```

### 4. Configure Environment

```bash
cp .env.example .env
nano .env  # Edit configuration
```

### 5. Create Systemd Service

Create `/etc/systemd/system/epmssts-api.service`:

```ini
[Unit]
Description=EPMSSTS API Service
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=epmssts
WorkingDirectory=/home/epmssts/EPMSSTS
Environment="PATH=/home/epmssts/EPMSSTS/venv/bin"
ExecStart=/home/epmssts/EPMSSTS/venv/bin/uvicorn epmssts.api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable epmssts-api
sudo systemctl start epmssts-api
sudo systemctl status epmssts-api
```

### 6. Nginx Reverse Proxy

Install Nginx:

```bash
sudo apt-get install nginx
```

Create `/etc/nginx/sites-available/epmssts`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts for long-running requests
        proxy_read_timeout 60s;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
    }
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/epmssts /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 7. SSL with Let's Encrypt

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Cloud Deployment

### AWS EC2

1. **Launch EC2 instance**
   - AMI: Ubuntu 22.04 LTS
   - Instance type: t3.xlarge (or g4dn.xlarge for GPU)
   - Storage: 50GB EBS
   - Security group: Allow ports 22, 80, 443, 8000

2. **Install Docker**
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker ubuntu
   ```

3. **Deploy application**
   ```bash
   git clone <repository-url>
   cd EPMSSTS
   docker-compose up -d
   ```

### Google Cloud Platform

1. **Create Compute Engine instance**
   ```bash
   gcloud compute instances create epmssts-instance \
     --machine-type=n1-standard-4 \
     --image-family=ubuntu-2204-lts \
     --image-project=ubuntu-os-cloud \
     --boot-disk-size=50GB
   ```

2. **SSH and deploy**
   ```bash
   gcloud compute ssh epmssts-instance
   # Follow Docker deployment steps
   ```

### Azure

1. **Create VM**
   ```bash
   az vm create \
     --resource-group epmssts-rg \
     --name epmssts-vm \
     --image UbuntuLTS \
     --size Standard_D4s_v3 \
     --admin-username azureuser
   ```

2. **Deploy application**
   ```bash
   ssh azureuser@<vm-ip>
   # Follow Docker deployment steps
   ```

## Monitoring

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Database connection
psql -U epmssts -d epmssts -c "SELECT 1;"

# Redis connection
redis-cli ping
```

### Logs

```bash
# Docker logs
docker-compose logs -f api

# Systemd logs
sudo journalctl -u epmssts-api -f

# Application logs
tail -f /var/log/epmssts/app.log
```

### Metrics

Monitor these key metrics:

- **Latency**: Average request duration
- **Throughput**: Requests per second
- **Error rate**: Failed requests percentage
- **Resource usage**: CPU, memory, disk
- **Model loading time**: Startup duration

### Prometheus + Grafana (Optional)

Add to `docker-compose.yml`:

```yaml
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
```

## Troubleshooting

### Common Issues

#### 1. Models not loading

**Symptom**: API fails to start or times out

**Solution**:
```bash
# Check disk space
df -h

# Check memory
free -h

# Increase timeout in docker-compose.yml
healthcheck:
  start_period: 300s  # 5 minutes
```

#### 2. Out of memory

**Symptom**: Container killed, OOM errors

**Solution**:
```bash
# Increase memory limit
docker-compose up -d --scale api=1 --memory=16g

# Or use CPU-only mode
export DEVICE=cpu
```

#### 3. Slow inference

**Symptom**: Requests timeout, high latency

**Solution**:
- Use GPU if available
- Reduce model size (not recommended for MVP)
- Scale horizontally with load balancer

#### 4. Database connection errors

**Symptom**: "could not connect to server"

**Solution**:
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check connection string
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT 1;"
```

#### 5. Redis connection errors

**Symptom**: "Error connecting to Redis"

**Solution**:
```bash
# Check Redis is running
docker-compose ps redis

# Test connection
redis-cli -u $REDIS_URL ping
```

### Debug Mode

Enable debug logging:

```bash
# In .env
LOG_LEVEL=DEBUG

# Restart service
docker-compose restart api
```

### Performance Tuning

1. **Database connection pooling**
   ```python
   # In .env
   DATABASE_POOL_SIZE=10
   DATABASE_MAX_OVERFLOW=20
   ```

2. **Redis caching**
   ```python
   # In .env
   REDIS_TTL_SECONDS=7200  # 2 hours
   ```

3. **Worker processes**
   ```bash
   # Run with multiple workers
   uvicorn epmssts.api.main:app --workers 4
   ```

## Backup and Recovery

### Database Backup

```bash
# Backup
pg_dump -U epmssts epmssts > backup.sql

# Restore
psql -U epmssts epmssts < backup.sql
```

### Automated Backups

Create cron job:

```bash
0 2 * * * pg_dump -U epmssts epmssts | gzip > /backups/epmssts_$(date +\%Y\%m\%d).sql.gz
```

## Security Checklist

- [ ] Change default passwords
- [ ] Enable HTTPS/SSL
- [ ] Configure firewall
- [ ] Set up authentication (if needed)
- [ ] Enable rate limiting
- [ ] Regular security updates
- [ ] Backup encryption
- [ ] Monitor access logs

## Scaling

### Horizontal Scaling

Use load balancer with multiple API instances:

```yaml
services:
  api:
    deploy:
      replicas: 3
```

### Vertical Scaling

Increase resources per instance:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '16'
          memory: 32G
```

---

For additional support, please open an issue on GitHub.
