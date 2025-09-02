# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A FastAI-based web application for classifying chess piece images. The model can identify six chess pieces: Bishop, King, Knight, Pawn, Queen, and Rook.

## Key Commands

### Local Development with Docker
```bash
docker build -t fastai-v3 . && docker run --rm -it -p 5000:5000 fastai-v3
```

### Run Server Locally
```bash
python app/server.py serve
```

## Architecture

### Core Components

- **app/server.py**: Main FastAI/Starlette server that:
  - Downloads pre-trained model from Google Drive on startup
  - Serves static files and HTML frontend
  - Provides `/analyze` endpoint for image classification
  - Runs on port from environment variable or defaults to 50000

- **Frontend**: Simple vanilla JavaScript interface in:
  - `app/view/index.html`: UI for image upload
  - `app/static/client.js`: Handles file selection and API calls
  - `app/static/style.css`: Styling

### Model Management

- Model (`export.pkl`) is downloaded from Google Drive URL at runtime
- Download URL is hardcoded in server.py: `export_file_url`
- Model is loaded using FastAI's `load_learner()`
- Classes are predefined: `['Bishop', 'King', 'Knight', 'Pawn', 'Queen', 'Rook']`

### Deployment Configuration

- **Dockerfile**: Python 3.7.9 base image with FastAI dependencies
- **Procfile**: Heroku deployment configuration
- **requirements.txt**: Pins specific PyTorch CPU versions for deployment
- Port configured via `PORT` environment variable

## Key Considerations

- The app uses CPU-only PyTorch versions for deployment efficiency
- Model file is not stored in repo to keep deployment lightweight
- CORS is enabled for all origins in the Starlette middleware
- Image processing uses FastAI's `open_image()` from BytesIO stream