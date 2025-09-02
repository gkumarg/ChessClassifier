import aiohttp
import asyncio
import uvicorn
import os
import logging
from pathlib import Path
from io import BytesIO
from typing import Optional
from datetime import datetime, timedelta
from collections import defaultdict

from fastai.vision.all import *
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import HTMLResponse, JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.status import HTTP_413_REQUEST_ENTITY_TOO_LARGE, HTTP_429_TOO_MANY_REQUESTS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
PORT = int(os.environ.get('PORT', 5000))
MODEL_URL = os.environ.get('MODEL_URL', 'https://drive.google.com/uc?export=download&id=1jZgwjgy8CcLOhGP5OLNa4gB9d_bJyvoM')
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:5000').split(',')
MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE_MB', 10)) * 1024 * 1024  # Convert MB to bytes
RATE_LIMIT_PER_MINUTE = int(os.environ.get('RATE_LIMIT_PER_MINUTE', 30))

export_file_name = 'export.pkl'
classes = ['Bishop', 'King', 'Knight', 'Pawn', 'Queen', 'Rook']
path = Path(__file__).parent

# Rate limiting storage
rate_limit_storage = defaultdict(list)

app = Starlette()

# Security middleware
app.add_middleware(
    CORSMiddleware, 
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.onrender.com"]
)

app.mount('/static', StaticFiles(directory='app/static'))


def check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit"""
    now = datetime.now()
    minute_ago = now - timedelta(minutes=1)
    
    # Clean old entries
    rate_limit_storage[client_ip] = [
        timestamp for timestamp in rate_limit_storage[client_ip]
        if timestamp > minute_ago
    ]
    
    # Check limit
    if len(rate_limit_storage[client_ip]) >= RATE_LIMIT_PER_MINUTE:
        return False
    
    # Add current request
    rate_limit_storage[client_ip].append(now)
    return True


async def download_file(url: str, dest: Path) -> None:
    """Download model file with error handling"""
    if dest.exists():
        logger.info(f"Model file already exists at {dest}")
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                response.raise_for_status()
                data = await response.read()
                with open(dest, 'wb') as f:
                    f.write(data)
                logger.info(f"Model downloaded successfully to {dest}")
    except Exception as e:
        logger.error(f"Failed to download model: {str(e)}")
        raise


async def setup_learner() -> Optional[object]:
    """Setup the learner with error handling"""
    try:
        await download_file(MODEL_URL, path / export_file_name)
        learn = load_learner(path / export_file_name)
        logger.info("Model loaded successfully")
        return learn
    except Exception as e:
        logger.error(f"Failed to setup learner: {str(e)}")
        return None


# Initialize model
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
learn = loop.run_until_complete(setup_learner())
if not learn:
    logger.warning("Model could not be loaded. Service will run with limited functionality.")


@app.route('/')
async def homepage(request: Request):
    """Serve the main page with security headers"""
    html_file = path / 'view' / 'index.html'
    content = html_file.open().read()
    
    response = HTMLResponse(content)
    # Add security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self';"
    )
    
    return response


@app.route('/analyze', methods=['POST'])
async def analyze(request: Request):
    """Analyze uploaded image with validation and error handling"""
    
    # Get client IP for rate limiting
    client_ip = request.client.host
    
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
    
    try:
        # Parse form data
        form = await request.form()
        
        if 'file' not in form:
            return JSONResponse({'error': 'No file provided'}, status_code=400)
        
        img_data = form['file']
        
        # Validate file type
        if not img_data.filename:
            return JSONResponse({'error': 'No filename provided'}, status_code=400)
        
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        file_ext = Path(img_data.filename).suffix.lower()
        
        if file_ext not in allowed_extensions:
            return JSONResponse(
                {'error': f'Invalid file type. Allowed types: {", ".join(allowed_extensions)}'},
                status_code=400
            )
        
        # Read and validate file size
        img_bytes = await img_data.read()
        
        if len(img_bytes) > MAX_FILE_SIZE:
            return JSONResponse(
                {'error': f'File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB'},
                status_code=HTTP_413_REQUEST_ENTITY_TOO_LARGE
            )
        
        if len(img_bytes) == 0:
            return JSONResponse({'error': 'Empty file provided'}, status_code=400)
        
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


@app.route('/health')
async def health_check(request: Request):
    """Health check endpoint"""
    return JSONResponse({
        'status': 'healthy',
        'model_loaded': learn is not None,
        'timestamp': datetime.now().isoformat()
    })


if __name__ == '__main__':
    uvicorn.run(
        app=app,
        host='0.0.0.0',
        port=PORT,
        log_level="info",
        access_log=True
    )