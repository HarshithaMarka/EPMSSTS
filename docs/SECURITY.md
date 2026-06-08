# Security Policy

## Overview

EPMSSTS takes security seriously. This document outlines our security practices and how to report security vulnerabilities.

## Security Best Practices

### 1. Environment Variables

**Never** commit `.env` files or sensitive data to version control.

```bash
# ✅ GOOD: Environment variables
DATABASE_URL=postgresql://user:pass@localhost:5432/db
REDIS_URL=redis://localhost:6379

# ❌ BAD: Hardcoded credentials
db_url = "postgresql://user:pass@localhost:5432/db"
```

Use `.env.example` as a template:
```bash
cp .env.example .env
# Edit .env with your production values
```

### 2. Secret Management

#### Database Credentials
- Use strong passwords (minimum 16 characters)
- Use separate credentials for dev, staging, and production
- Rotate credentials regularly
- Never share credentials via unsecured channels

#### API Keys
- Store in environment variables only
- Rotate regularly
- Use different keys for different environments
- Implement key expiration

#### SSL/TLS Certificates
- Use valid certificates in production
- Renew before expiration
- Use secure cipher suites
- Enable HSTS headers

### 3. Database Security

#### PostgreSQL
```sql
-- Create strong password for postgres user
CREATE USER epmssts WITH PASSWORD 'strong_password_here';

-- Grant minimal required privileges
GRANT CONNECT ON DATABASE epmssts TO epmssts;
GRANT USAGE ON SCHEMA public TO epmssts;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO epmssts;

-- Enable SSL
ssl = on
```

#### Connection Security
- Always use SSL/TLS for database connections in production
- Use connection pooling (PgBouncer)
- Limit database user privileges
- Whitelist IP addresses when possible

### 4. Input Validation

All user inputs are validated using Pydantic:

```python
from pydantic import BaseModel, Field, validator

class TranslationRequest(BaseModel):
    source_lang: str = Field(..., min_length=2, max_length=5)
    target_lang: str = Field(..., min_length=2, max_length=5)
    text: str = Field(..., min_length=1, max_length=5000)
    
    @validator('text')
    def validate_text(cls, v):
        # Remove suspicious characters
        return v.strip()
```

### 5. File Upload Security

```python
# Configured in config.py
MAX_FILE_SIZE_MB = 10
ALLOWED_AUDIO_TYPES = ["audio/wav", "audio/mpeg", "audio/flac"]

# Validation in endpoints
if file.size > settings.max_file_size_mb * 1024 * 1024:
    raise HTTPException(status_code=400, detail="File too large")

if file.content_type not in settings.allowed_audio_types:
    raise HTTPException(status_code=400, detail="Invalid file type")
```

### 6. SQL Injection Prevention

All database queries use parameterized statements:

```python
# ✅ GOOD: Parameterized query
cursor.execute(
    "SELECT * FROM translation_logs WHERE session_id = %s",
    (session_id,)
)

# ❌ BAD: String concatenation
cursor.execute(f"SELECT * FROM translation_logs WHERE session_id = '{session_id}'")
```

### 7. CORS Configuration

Control which origins can access the API:

```env
# .env
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# NOT for production
CORS_ORIGINS=*  # Only for development!
```

### 8. Rate Limiting

Rate limiting is available in config:

```env
# .env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST=10
```

## Authentication & Authorization

### Current State
- **v1.0.0**: No authentication required
- **Recommended for Production**: Implement API key or OAuth2

### Future Implementation

```python
# Recommended pattern for v1.1.0+
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key
```

## Deployment Security

### Docker Security

```dockerfile
# Use non-root user
RUN useradd -m appuser
USER appuser

# Don't run as root
# ❌ BAD
RUN pip install -r requirements.txt
CMD ["python", "app.py"]

# ✅ GOOD
RUN pip install --user -r requirements.txt
USER appuser
CMD ["python", "app.py"]
```

### Environment-Specific Security

#### Development
```env
DEBUG=true
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ORIGINS=http://localhost:8501
```

#### Production
```env
DEBUG=false
ALLOWED_HOSTS=yourdomain.com
CORS_ORIGINS=https://yourdomain.com
RATE_LIMIT_ENABLED=true
SSL_ENABLED=true
```

### SSL/TLS Configuration

For production with Let's Encrypt:

```bash
# Using Certbot
certbot certonly --standalone -d yourdomain.com

# Update nginx/reverse proxy to use certificates
ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
```

## Monitoring & Logging

### Enable Security Logging

```env
# .env
LOG_LEVEL=INFO
LOG_FORMAT=json

# Log rotation
LOG_MAX_SIZE=100MB
LOG_BACKUP_COUNT=10
```

### Monitor These Events
- Failed authentication attempts
- Unusual API usage patterns
- Database errors
- Large file uploads
- Slow queries

### Review Logs Regularly
```bash
# Check API logs
docker-compose logs api | grep ERROR

# Check database logs
docker-compose logs postgres | grep ERROR

# Monitor in production
tail -f /var/log/epmssts/app.log
```

## Dependency Security

### Keep Dependencies Updated

```bash
# Check for vulnerable packages
pip list --outdated
pip-audit

# Update safely
pip install --upgrade -r requirements.txt

# Pin versions for reproducibility
pip freeze > requirements-locked.txt
```

### Vulnerable Package Response

If a security vulnerability is found in a dependency:

1. **Immediate**: Disable affected functionality if possible
2. **Short-term**: Update package to patched version
3. **Long-term**: Monitor for better alternatives if needed

## API Security

### Endpoint Protection

```python
from fastapi import Depends, HTTPException, status

async def require_api_key(api_key: str = Header(...)) -> str:
    if api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )
    return api_key

@app.post("/translate/speech")
async def translate_speech(
    file: UploadFile = File(...),
    api_key: str = Depends(require_api_key)
):
    # Protected endpoint
    pass
```

## Data Protection

### Sensitive Data Handling

- Never log user input or API responses containing sensitive data
- Encrypt data at rest (database encryption)
- Encrypt data in transit (HTTPS/TLS)
- Implement data retention policies
- Secure deletion of logs after retention period

### GDPR/Privacy Compliance

```python
# Example: Delete user data on request
@app.delete("/user/{user_id}/data")
async def delete_user_data(user_id: str):
    """Delete all user data from system."""
    # Delete from PostgreSQL
    db.execute(
        "DELETE FROM translation_logs WHERE user_id = %s",
        (user_id,)
    )
    # Delete from Redis cache
    cache.delete(f"session:{user_id}:*")
    return {"status": "deleted"}
```

## Reporting Security Vulnerabilities

### Do Not Create Public Issues

If you discover a security vulnerability:

1. **Do NOT** create a public GitHub issue
2. **Do** email the security team: security@example.com
3. **Include**: Vulnerability description, affected version, proof of concept
4. **Wait**: Allow 48 hours for acknowledgment, 7 days for fix attempt

### Responsible Disclosure

We follow responsible disclosure practices:
- Acknowledge receipt within 24 hours
- Provide update within 7 days
- Deploy fix and notify within 30 days
- Credit reporter in changelog (if desired)

## Security Checklist for Deployment

- [ ] `.env` file created and not committed
- [ ] Database credentials changed from defaults
- [ ] SSL/TLS certificates installed
- [ ] CORS_ORIGINS configured correctly
- [ ] DEBUG mode disabled
- [ ] Rate limiting enabled
- [ ] Firewall rules configured
- [ ] Regular backups scheduled
- [ ] Monitoring and logging enabled
- [ ] Security team assigned
- [ ] Incident response plan documented
- [ ] Dependencies up to date
- [ ] Load balancer configured (if applicable)

## Incident Response

### If a Security Issue is Discovered

1. **Isolate**: Disable affected service if needed
2. **Investigate**: Understand scope and impact
3. **Notify**: Alert relevant stakeholders
4. **Fix**: Apply patch or workaround
5. **Test**: Verify fix doesn't introduce new issues
6. **Deploy**: Push fix to production
7. **Document**: Write incident report

### Incident Report Template

```markdown
# Security Incident Report

**Date:** YYYY-MM-DD  
**Severity:** [Critical|High|Medium|Low]  
**Status:** [Open|Resolved]  

## Description
Brief description of the incident

## Impact
What systems/data were affected

## Root Cause
Why did this happen

## Resolution
What was done to fix it

## Prevention
How to prevent this in future
```

## Security Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [PostgreSQL Security](https://www.postgresql.org/docs/current/sql-syntax.html)
- [Docker Security](https://docs.docker.com/engine/security/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

## Support

For security questions or concerns:
- Email: security@example.com
- PGP Key: [if applicable]
- Security Policy: This file

---

**Last Updated:** January 29, 2026  
**Version:** 1.0  
**Maintained by:** EPMSSTS Security Team
