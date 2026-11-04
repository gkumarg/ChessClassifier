import aiohttp
import asyncio
import hashlib
import hmac
import uvicorn
import os
import logging
from pathlib import Path
from io import BytesIO
from typing import Optional
from datetime import datetime, timedelta
from collections import defaultdict

from fastai.vision.all import *
from PIL import Image, UnidentifiedImageError
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_411_LENGTH_REQUIRED,
    HTTP_413_CONTENT_TOO_LARGE,
    HTTP_429_TOO_MANY_REQUESTS,
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
PORT = int(os.environ.get('PORT', 5000))
MODEL_URL = os.environ.get('MODEL_URL', 'https://github.com/gkumarg/ChessClassifier/releases/download/v0.1/export.pkl')
# SHA-256 of the trusted model file. load_learner() unpickles the file, which can execute
# arbitrary code, so the model is only loaded if its hash matches. Override when MODEL_URL changes.
MODEL_SHA256 = os.environ.get('MODEL_SHA256', '4c377e71a4dee21f6ea2732967e783eab708f59fb4e749a1f81818f60f22c80d').strip().lower()
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:5000').split(',')
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,*.onrender.com').split(',')
MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE_MB', 10)) * 1024 * 1024  # Convert MB to bytes
MAX_REQUEST_SIZE = MAX_FILE_SIZE + 64 * 1024  # Allow for multipart framing overhead
RATE_LIMIT_PER_MINUTE = int(os.environ.get('RATE_LIMIT_PER_MINUTE', 30))

# Reject decompression bombs: Pillow raises DecompressionBombError above 2x this pixel count
Image.MAX_IMAGE_PIXELS = 25_000_000
ALLOWED_IMAGE_FORMATS = {'JPEG', 'PNG', 'GIF', 'BMP', 'WEBP'}

export_file_name = 'export.pkl'
classes = ['Bishop', 'King', 'Knight', 'Pawn', 'Queen', 'Rook']
path = Path(__file__).parent

SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Content-Security-Policy': (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    ),
}

# Rate limiting storage
rate_limit_storage = defaultdict(list)


def check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit"""
    now = datetime.now()
    minute_ago = now - timedelta(minutes=1)

    # Drop expired entries, and idle clients entirely so the table cannot grow without bound
    for ip in list(rate_limit_storage):
        recent = [t for t in rate_limit_storage[ip] if t > minute_ago]
        if recent:
            rate_limit_storage[ip] = recent
        else:
            del rate_limit_storage[ip]

    # Check limit
    if len(rate_limit_storage[client_ip]) >= RATE_LIMIT_PER_MINUTE:
        return False

    # Add current request
    rate_limit_storage[client_ip].append(now)
    return True


def sha256_of(file_path: Path) -> str:
    digest = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


async def download_file(url: str, dest: Path) -> None:
    """Download model file with error handling"""
    if dest.exists():
        logger.info(f"Model file already exists at {dest}")
        return

    tmp = dest.with_suffix(dest.suffix + '.part')
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                response.raise_for_status()
                with open(tmp, 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        f.write(chunk)
        tmp.replace(dest)
        logger.info(f"Model downloaded successfully to {dest}")
    except Exception as e:
        tmp.unlink(missing_ok=True)
        logger.error(f"Failed to download model: {str(e)}")
        raise


async def setup_learner() -> Optional[object]:
    """Setup the learner with error handling"""
    model_path = path / export_file_name
    try:
        await download_file(MODEL_URL, model_path)
        actual = sha256_of(model_path)
        if not hmac.compare_digest(actual, MODEL_SHA256):
            logger.error(f"Model checksum mismatch (expected {MODEL_SHA256}, got {actual}); refusing to load it")
            model_path.unlink(missing_ok=True)
            return None
        learn = load_learner(model_path)
        logger.info("Model loaded successfully")
        return learn
    except Exception as e:
        logger.error(f"Failed to setup learner: {str(e)}")
        return None


# Initialize model
learn = asyncio.run(setup_learner())
if not learn:
    logger.warning("Model could not be loaded. Service will run with limited functionality.")


async def homepage(request: Request):
    """Serve the main page"""
    return HTMLResponse((path / 'view' / 'index.html').read_text(encoding='utf-8'))


async def analyze(request: Request):
    """Analyze uploaded image with validation and error handling"""

    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else 'unknown'

    # Check rate limit
    if not check_rate_limit(client_ip):
        return JSONResponse(
            {'error': 'Rate limit exceeded. Please try again later.'},
            status_code=HTTP_429_TOO_MANY_REQUESTS
        )

    # Check if model is loaded
    if not learn:
        return JSONResponse(
            {'error': 'Model not available. Please try again later.'},
            status_code=503
        )

    # Reject oversized bodies before parsing them
    content_length = request.headers.get('content-length')
    if content_length is None or not content_length.isdigit():
        return JSONResponse({'error': 'Content-Length header required'}, status_code=HTTP_411_LENGTH_REQUIRED)
    if int(content_length) > MAX_REQUEST_SIZE:
        return JSONResponse(
            {'error': f'File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB'},
            status_code=HTTP_413_CONTENT_TOO_LARGE
        )

    try:
        # Parse form data
        form = await request.form(max_files=1, max_fields=5)

        if 'file' not in form:
            return JSONResponse({'error': 'No file provided'}, status_code=HTTP_400_BAD_REQUEST)

        img_data = form['file']

        # Validate file type
        if isinstance(img_data, str) or not img_data.filename:
            return JSONResponse({'error': 'No filename provided'}, status_code=HTTP_400_BAD_REQUEST)

        allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        file_ext = Path(img_data.filename).suffix.lower()

        if file_ext not in allowed_extensions:
            return JSONResponse(
                {'error': f'Invalid file type. Allowed types: {", ".join(sorted(allowed_extensions))}'},
                status_code=HTTP_400_BAD_REQUEST
            )

        # Read and validate file size
        img_bytes = await img_data.read()

        if len(img_bytes) > MAX_FILE_SIZE:
            return JSONResponse(
                {'error': f'File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB'},
                status_code=HTTP_413_CONTENT_TOO_LARGE
            )

        if len(img_bytes) == 0:
            return JSONResponse({'error': 'Empty file provided'}, status_code=HTTP_400_BAD_REQUEST)

        # Validate the actual content, not just the extension
        try:
            with Image.open(BytesIO(img_bytes)) as probe:
                image_format = probe.format
                probe.verify()
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
            image_format = None
        if image_format not in ALLOWED_IMAGE_FORMATS:
            return JSONResponse({'error': 'File is not a valid image'}, status_code=HTTP_400_BAD_REQUEST)

        # Process image
        img = PILImage.create(BytesIO(img_bytes))

        # Make prediction
        prediction, _, probs = learn.predict(img)

        # Get confidence score
        confidence = float(probs.max())

        return JSONResponse({
            'result': str(prediction),
            'confidence': f'{confidence:.2%}',
            'all_probabilities': {
                cls: f'{float(prob):.2%}'
                for cls, prob in zip(classes, probs)
            }
        })

    except Exception as e:
        logger.error(f"Error processing image: {str(e)}", exc_info=True)
        return JSONResponse(
            {'error': 'Failed to process image. Please ensure the file is a valid image.'},
            status_code=500
        )


async def health_check(request: Request):
    """Health check endpoint"""
    return JSONResponse({
        'status': 'healthy',
        'model_loaded': learn is not None,
        'timestamp': datetime.now().isoformat()
    })


class SecurityHeadersMiddleware:
    """Add security headers to every HTTP response"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers', []))
                headers.extend((k.lower().encode(), v.encode()) for k, v in SECURITY_HEADERS.items())
                message['headers'] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


app = Starlette(
    routes=[
        Route('/', homepage),
        Route('/analyze', analyze, methods=['POST']),
        Route('/health', health_check),
        Mount('/static', StaticFiles(directory=path / 'static')),
    ],
    middleware=[
        Middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS),
        Middleware(
            CORSMiddleware,
            allow_origins=ALLOWED_ORIGINS,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        ),
        Middleware(SecurityHeadersMiddleware),
    ],
)


if __name__ == '__main__':
    uvicorn.run(
        app=app,
        host='0.0.0.0',
        port=PORT,
        log_level="info",
        access_log=True
    )
