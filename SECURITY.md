# Security Updates and Best Practices

## Recent Security Improvements

### 1. Dependency Updates
- **Python**: 3.13
- **FastAI**: 2.7.19 (latest 2.7.x; fastai>=2.8 cannot load the published export.pkl)
- **PyTorch**: 2.6.0 / torchvision 0.21.0 (highest versions fastai 2.7.19 allows; CPU-only wheels in Docker)
- **Starlette**: 1.10.0, **uvicorn**: 0.54.0, **aiohttp**: 3.14.5, **Pillow**: 13.0.0, **numpy**: 2.4.6
- Re-exporting the model with fastai>=2.8 would allow moving to current torch releases

### Model Integrity
- `load_learner()` unpickles the model, which can execute arbitrary code
- The downloaded model's SHA-256 is checked against `MODEL_SHA256` before loading; a mismatch is refused and the file deleted
- Downloads are streamed to a temporary file and only moved into place once complete

### 2. Server Security Enhancements

#### Input Validation
- File size limits (10MB max)
- Oversized requests rejected from `Content-Length` before the body is parsed
- File type validation by extension and by decoded image format (JPEG, PNG, GIF, BMP, WebP)
- Decompression-bomb protection via Pillow's pixel limit
- Filename sanitization
- Empty file checks

#### Rate Limiting
- 30 requests per minute per IP (configurable)
- In-memory rate limiting; idle clients are evicted so memory stays bounded
- Behind a proxy, set `FORWARDED_ALLOW_IPS` so uvicorn uses the real client IP

#### Security Headers (on every response)
- Content-Security-Policy with no `unsafe-inline` (the frontend uses no inline scripts or styles)
- X-Frame-Options: DENY / `frame-ancestors 'none'`
- X-Content-Type-Options: nosniff
- Referrer-Policy: strict-origin-when-cross-origin

#### Frontend
- Results are rendered with DOM nodes and `textContent`, never `innerHTML`

#### CORS Configuration
- Configurable allowed origins (no longer wildcard)
- Credentials disabled (the app uses no cookies)
- Allowed hosts configurable via `ALLOWED_HOSTS`

#### Error Handling
- Generic error messages to prevent information leakage
- Proper logging without exposing sensitive data
- Graceful model loading failures

### 3. Docker Security
- Non-root user execution
- Minimal base image (python:3.13-slim), no compiler toolchain
- Health checks included
- No cache for pip installations

### 4. Configuration Management
- Environment variables for sensitive data
- .env file support with python-dotenv
- Example configuration file provided
- Model URL no longer hardcoded

## Configuration

Create a `.env` file based on `.env.example`:

```env
PORT=5000
MODEL_URL=your_model_url_here
MODEL_SHA256=sha256_of_that_model
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com
ALLOWED_ORIGINS=http://localhost:5000,https://yourdomain.com
MAX_FILE_SIZE_MB=10
RATE_LIMIT_PER_MINUTE=30
```

## Security Checklist

✅ Dependencies updated to latest versions
✅ Input validation on all user inputs
✅ Rate limiting implemented
✅ Security headers configured
✅ CORS properly configured
✅ Error handling prevents information leakage
✅ Docker container runs as non-root user
✅ Environment variables for configuration
✅ File size and type restrictions
✅ Request timeouts configured
✅ Health check endpoint available

## Monitoring

The application includes:
- Structured logging with timestamps
- Health check endpoint at `/health`
- Error tracking with stack traces (in logs only)

## Future Recommendations

1. Add authentication for production use
2. Implement database for persistent rate limiting
3. Add request signing/validation
4. Consider using a reverse proxy (nginx) in production
5. Implement monitoring and alerting
6. Add automated security scanning in CI/CD
7. Regular dependency updates schedule
8. Consider implementing CAPTCHA for additional bot protection