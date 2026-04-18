# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 4.x     | ✅        |
| < 4.0   | ❌        |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Email the maintainer directly with details
3. Include steps to reproduce the vulnerability
4. Allow reasonable time for a fix before public disclosure

## Security Measures

IND-Diplomat implements the following security controls:

### Authentication & Authorization
- JWT-based authentication with role-based access control (RBAC)
- API key validation for service-to-service communication
- Bcrypt password hashing with configurable rounds

### Input Validation
- Scope guard prevents injection of off-topic queries
- PII masking in pipeline outputs
- Input sanitization before LLM submission

### Output Safety
- Safety review gate before any assessment is released
- Human-in-the-loop (HITL) flagging for high-impact predictions
- Refusal engine for queries that fail safety checks

### Infrastructure
- Non-root container execution
- Health check endpoints for orchestration
- CORS configuration with credential-aware origin matching
- Environment-based secret management (no hardcoded credentials)

### Data Protection
- Sensitive keys are redacted in all log output
- Runtime artifacts excluded from version control
- SQLite databases excluded from git

## Configuration Hardening

For production deployments:

```env
# Change all default secrets
API_KEY=<strong-random-key>
JWT_SECRET_KEY=<strong-random-key>

# Restrict CORS origins
CORS_ALLOWED_ORIGINS=https://your-domain.com

# Disable demo users
AUTH_ENABLE_DEMO_USERS=false
AUTH_STRICT_SECURITY=true
```
