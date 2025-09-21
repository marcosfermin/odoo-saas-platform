# Customer Portal Service

The customer portal service provides self-service capabilities for customers to manage their Odoo SaaS tenants, billing, and support tickets.

## Features

### Authentication & Authorization
- JWT-based authentication
- Customer registration and login
- Password reset functionality
- Rate limiting for security

### Tenant Management
- Create and manage Odoo tenants
- Install/uninstall Odoo modules
- Monitor tenant status and resources
- Access tenant logs and backups
- Custom subdomain configuration

### Billing Integration
- View available subscription plans
- Subscribe to plans via Stripe or Paddle
- Manage payment methods
- View invoices and payment history
- Usage monitoring and billing alerts
- Subscription management (upgrade/downgrade/cancel)

### Support System
- Create and manage support tickets
- Track ticket status and responses
- Priority-based ticket handling
- Category-based ticket organization
- Customer communication history

### Webhook Handlers
- Stripe webhook processing
- Paddle webhook processing
- Payment event tracking
- Subscription lifecycle management
- Automatic status synchronization

## API Endpoints

### Authentication (`/api/auth`)
- `POST /register` - Customer registration
- `POST /login` - Customer login
- `POST /logout` - Customer logout
- `GET /profile` - Get customer profile
- `PUT /profile` - Update customer profile
- `POST /change-password` - Change password
- `POST /forgot-password` - Request password reset
- `POST /reset-password` - Reset password with token

### Tenants (`/api/tenants`)
- `GET /` - List customer tenants
- `POST /` - Create new tenant
- `GET /<id>` - Get tenant details
- `PUT /<id>` - Update tenant
- `DELETE /<id>` - Delete tenant
- `GET /<id>/modules` - List available modules
- `POST /<id>/modules` - Install module
- `DELETE /<id>/modules/<module>` - Uninstall module
- `GET /<id>/logs` - Get tenant logs
- `POST /<id>/backup` - Create tenant backup
- `GET /<id>/backups` - List tenant backups

### Billing (`/api/billing`)
- `GET /plans` - List available plans
- `GET /subscriptions` - List customer subscriptions
- `POST /subscribe` - Create new subscription
- `PUT /subscriptions/<id>/cancel` - Cancel subscription
- `GET /invoices` - List customer invoices
- `GET /payment-methods` - List payment methods
- `POST /payment-methods` - Add payment method
- `DELETE /payment-methods/<id>` - Remove payment method
- `POST /checkout/stripe` - Create Stripe checkout session
- `POST /checkout/paddle` - Create Paddle checkout session
- `GET /usage` - Get usage metrics

### Support (`/api/support`)
- `GET /` - List support tickets
- `POST /` - Create support ticket
- `GET /<id>` - Get ticket details
- `PUT /<id>` - Update ticket (add response)
- `POST /<id>/close` - Close ticket
- `GET /stats` - Get ticket statistics

### Webhooks (`/api/webhooks`)
- `POST /stripe` - Stripe webhook handler
- `POST /paddle` - Paddle webhook handler

### Health (`/api/health`)
- `GET /` - Health check
- `GET /ready` - Readiness check (Kubernetes)
- `GET /live` - Liveness check (Kubernetes)

## Configuration

The portal service uses environment variables for configuration:

```bash
# Flask Configuration
FLASK_ENV=development
FLASK_SECRET_KEY=your-secret-key-here
PORT=5001
HOST=127.0.0.1

# Database
DATABASE_URL=postgresql://user:password@localhost/odoo_saas
SQLALCHEMY_TRACK_MODIFICATIONS=false

# JWT Configuration
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ACCESS_TOKEN_EXPIRES=3600  # 1 hour
JWT_REFRESH_TOKEN_EXPIRES=2592000  # 30 days

# Rate Limiting
RATELIMIT_STORAGE_URL=redis://localhost:6379/0
RATELIMIT_DEFAULT="100 per hour"

# CORS
CORS_ORIGINS=["http://localhost:3000", "https://yourdomain.com"]

# Stripe Configuration
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_SIGNING_SECRET=whsec_...

# Paddle Configuration
PADDLE_VENDOR_ID=12345
PADDLE_API_KEY=your-paddle-api-key
PADDLE_PUBLIC_KEY_BASE64=your-paddle-public-key

# Email Configuration (for notifications)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=noreply@yourdomain.com

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/portal.log

# Redis (for caching and rate limiting)
REDIS_URL=redis://localhost:6379/0

# Monitoring
PROMETHEUS_METRICS_PATH=/metrics
PROMETHEUS_METRICS_PORT=9090
```

## Development Setup

### Prerequisites
- Python 3.9+
- PostgreSQL 12+
- Redis 6+

### Installation

1. Create virtual environment:
```bash
cd portal/
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Initialize database:
```bash
python run.py init-db
python run.py seed-db
```

5. Run the application:
```bash
python run.py
```

The portal will be available at `http://127.0.0.1:5001`

### Development Commands

```bash
# Initialize database
python run.py init-db

# Seed database with sample data
python run.py seed-db

# Run tests
python run.py test
# or
pytest

# Run with debug mode
FLASK_ENV=development python run.py
```

## Docker Deployment

### Build Image
```bash
docker build -t odoo-saas-portal .
```

### Run Container
```bash
docker run -d \
  --name portal \
  -p 5001:5001 \
  -e DATABASE_URL=postgresql://user:pass@host/db \
  -e REDIS_URL=redis://redis:6379/0 \
  -e JWT_SECRET_KEY=your-secret \
  odoo-saas-portal
```

### Docker Compose
See the main project's `docker-compose.yml` for the complete setup.

## API Authentication

Most endpoints require JWT authentication. Include the token in the Authorization header:

```http
Authorization: Bearer <your-jwt-token>
```

### Getting a Token

```bash
# Register a new customer
curl -X POST http://localhost:5001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "customer@example.com",
    "password": "SecurePass123!",
    "company_name": "My Company",
    "first_name": "John",
    "last_name": "Doe"
  }'

# Login to get tokens
curl -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "customer@example.com",
    "password": "SecurePass123!"
  }'
```

## Rate Limiting

The API implements rate limiting to prevent abuse:

- Authentication endpoints: 5 requests per minute
- Tenant creation: 3 requests per minute
- General API: 60 requests per minute
- Support tickets: 10 requests per minute

Rate limits are tracked per customer (when authenticated) or per IP address.

## Error Handling

The API returns consistent error responses:

```json
{
  "error": "Description of the error",
  "code": "ERROR_CODE",
  "details": {
    "field": "specific error details"
  }
}
```

Common HTTP status codes:
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `429` - Rate Limited
- `500` - Internal Server Error

## Testing

### Unit Tests
```bash
pytest tests/unit/
```

### Integration Tests
```bash
pytest tests/integration/
```

### API Tests
```bash
pytest tests/api/
```

### Coverage Report
```bash
pytest --cov=portal --cov-report=html
```

## Monitoring

### Health Checks
- `GET /api/health` - Basic health check
- `GET /api/health/ready` - Readiness probe for Kubernetes
- `GET /api/health/live` - Liveness probe for Kubernetes

### Metrics
Prometheus metrics are available at `/metrics`:
- Request count and duration
- Error rates
- Authentication events
- Database connection pool stats
- Rate limiting stats

### Logging
Structured JSON logs include:
- Request/response details
- Authentication events
- Error traces
- Performance metrics

## Security

### Authentication Security
- Passwords are hashed using Werkzeug (PBKDF2)
- JWT tokens have configurable expiration
- Rate limiting prevents brute force attacks
- Failed login attempts are logged

### API Security
- CORS configuration for cross-origin requests
- Input validation using JSON schemas
- SQL injection prevention via SQLAlchemy ORM
- XSS prevention through proper output encoding

### Webhook Security
- Stripe webhook signature verification
- Paddle webhook signature verification (configurable)
- Idempotency checks to prevent duplicate processing

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Check DATABASE_URL environment variable
   - Ensure PostgreSQL is running
   - Verify database exists and permissions

2. **JWT Token Issues**
   - Check JWT_SECRET_KEY is set
   - Verify token hasn't expired
   - Ensure clock synchronization

3. **Rate Limiting Issues**
   - Check Redis connection
   - Verify RATELIMIT_STORAGE_URL
   - Clear rate limit data if needed

4. **Webhook Processing Failures**
   - Check webhook endpoint URLs
   - Verify signature secrets
   - Review webhook logs

### Debugging

Enable debug mode:
```bash
FLASK_ENV=development python run.py
```

Check logs:
```bash
tail -f logs/portal.log
```

Database debugging:
```bash
# Connect to database
psql $DATABASE_URL

# Check tables
\dt

# Check recent customer registrations
SELECT * FROM customers ORDER BY created_at DESC LIMIT 10;
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run the test suite
5. Submit a pull request

### Code Style
- Follow PEP 8
- Use type hints where appropriate
- Document functions and classes
- Write tests for new features

## License

This project is licensed under the MIT License. See the LICENSE file for details.