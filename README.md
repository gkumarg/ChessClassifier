# Chess Piece Classifier

A small web app that identifies chess pieces in photos. Upload an image and a fastai model classifies it as one of six pieces: **Bishop, King, Knight, Pawn, Queen or Rook**. The app shows the top prediction and the probability for each class.

It's built on [fastai](https://github.com/fastai/fastai) and [Starlette](https://www.starlette.io/), and runs in a single Docker container on CPU.

## Features

- Single-page UI: pick an image, click **Analyze**, see the result
- JSON API for programmatic use (`POST /analyze`)
- Model is downloaded at startup and verified against a SHA-256 checksum before loading
- Upload validation (size, extension and actual image format), per-IP rate limiting, strict security headers
- CPU-only PyTorch, so the image runs on free-tier hosting

## Quick start (Docker)

```bash
docker build -t chess-classifier .
docker run --rm -p 5000:5000 chess-classifier
```

Open http://localhost:5000. On first start the container downloads the model (about 85 MB), so the first request may take a minute.

## Running without Docker

Requires Python 3.11 or newer (3.13 is what the Docker image uses).

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install --index-url https://download.pytorch.org/whl/cpu torch==2.6.0 torchvision==0.21.0
pip install -r requirements.txt
python app/server.py
```

> **Windows note:** the published model was exported on Linux and doesn't load on native Windows Python (`cannot instantiate 'PosixPath'`). Use Docker or WSL on Windows.

## Configuration

Settings are read from environment variables or a `.env` file. Copy [.env.example](.env.example) to `.env` to get started.

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `5000` | Port the server listens on |
| `MODEL_URL` | v0.1 GitHub release | Where to download `export.pkl` from |
| `MODEL_SHA256` | hash of the v0.1 model | Expected SHA-256 of the model; a mismatched file is refused |
| `ALLOWED_ORIGINS` | `http://localhost:5000` | Comma-separated CORS origins |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,*.onrender.com` | Comma-separated hostnames the server answers to |
| `MAX_FILE_SIZE_MB` | `10` | Maximum upload size |
| `RATE_LIMIT_PER_MINUTE` | `30` | `/analyze` requests allowed per client IP per minute |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | Proxy IPs trusted for `X-Forwarded-For`; set this behind a reverse proxy so rate limiting sees real client IPs |

If you point `MODEL_URL` at a different model, update `MODEL_SHA256` too:

```bash
sha256sum export.pkl
```

## API

### `POST /analyze`

Send the image as multipart form data in a field named `file`.

```bash
curl -F "file=@knight.jpg" http://localhost:5000/analyze
```

Example response:

```json
{
  "result": "Knight",
  "confidence": "91.37%",
  "all_probabilities": {
    "Bishop": "2.10%",
    "King": "1.05%",
    "Knight": "91.37%",
    "Pawn": "0.88%",
    "Queen": "3.02%",
    "Rook": "1.58%"
  }
}
```

| Status | Meaning |
|---|---|
| `200` | Prediction returned |
| `400` | Missing file, unsupported type, or not a valid image |
| `411` | `Content-Length` header missing |
| `413` | File larger than `MAX_FILE_SIZE_MB` |
| `429` | Rate limit exceeded |
| `503` | Model not loaded (download failed or checksum mismatch) |

Accepted formats: JPEG, PNG, GIF, BMP, WebP.

### `GET /health`

Returns `{"status": "healthy", "model_loaded": true, ...}`. The Docker image uses this for its health check.

## Deployment

The repo deploys as-is to any host that builds a Dockerfile (Render, Fly.io, Railway and similar). A `Procfile` and `runtime.txt` are also included for buildpack-based hosts.

For a public deployment:

1. Set `ALLOWED_HOSTS` and `ALLOWED_ORIGINS` to your domain.
2. Set `FORWARDED_ALLOW_IPS` if the host puts a proxy in front of the app (most do), otherwise every visitor shares one rate limit.
3. Give the instance at least 1 GB of RAM; PyTorch and the model need roughly that to load.

## Project structure

```
app/
  server.py         Starlette app: model download, validation, inference
  view/index.html   Frontend page
  static/           client.js and style.css
Dockerfile          Python 3.13 slim image, CPU-only PyTorch
requirements.txt    Pinned dependencies
.env.example        Configuration template
```

## About the model

The model is a fastai CNN classifier exported with fastai 2.7. It's published as a [GitHub release asset](https://github.com/gkumarg/ChessClassifier/releases/tag/v0.1) rather than committed to the repo.

Because the export was made with fastai 2.7, the app is pinned to fastai 2.7.x, which in turn limits PyTorch to 2.6. Re-exporting the model with fastai 2.8 or newer would allow upgrading both.

## Security

See [SECURITY.md](SECURITY.md) for how to report a vulnerability and for details of the app's hardening.

## Acknowledgements

Originally based on the [fast.ai Render deployment starter](https://course.fast.ai/deployment_render.html).

## License

[MIT](LICENSE)
