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
  - Downloads pre-trained model from a GitHub release on startup and verifies its SHA-256
  - Serves static files and HTML frontend
  - Provides `/analyze` endpoint for image classification
  - Runs on port from `PORT` environment variable or defaults to 5000

- **Frontend**: Simple vanilla JavaScript interface in:
  - `app/view/index.html`: UI for image upload
  - `app/static/client.js`: Handles file selection and API calls
  - `app/static/style.css`: Styling

### Model Management

- Model (`export.pkl`) is downloaded from `MODEL_URL` at runtime and only loaded if it matches `MODEL_SHA256`
- The model was pickled with fastai 2.7, so fastai must stay <2.8 (which caps torch <2.7) until it is re-exported
- Model is loaded using FastAI's `load_learner()`
- Classes are predefined: `['Bishop', 'King', 'Knight', 'Pawn', 'Queen', 'Rook']`

### Deployment Configuration

- **Dockerfile**: Python 3.13 slim base image; installs CPU-only torch before requirements
- **Procfile**: Heroku deployment configuration
- **requirements.txt**: Pins exact versions of all direct dependencies
- Port configured via `PORT` environment variable

## Key Considerations

- The app uses CPU-only PyTorch versions for deployment efficiency
- Model file is not stored in repo to keep deployment lightweight
- CORS is restricted to `ALLOWED_ORIGINS`; hosts to `ALLOWED_HOSTS`
- Uploads are validated by size, extension and decoded image format, then classified with `PILImage.create()`