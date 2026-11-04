# Security Policy

## Supported versions

Only the latest commit on `master` receives security fixes.

## Reporting a vulnerability

Please **don't open a public issue** for security problems.

Report them privately through GitHub instead: go to the repository's **Security** tab and click **Report a vulnerability**. Include what you found, how to reproduce it, and the impact you expect.

This is a personal project maintained in spare time, so there's no guaranteed response time, but reports will be acknowledged and fixed as soon as practical.

## Security measures in the app

- **Model integrity:** the model file is unpickled on load, which can execute code, so the server checks its SHA-256 against `MODEL_SHA256` first and refuses a file that doesn't match.
- **Upload validation:** oversized requests are rejected before parsing; uploads are checked by extension and by decoded image format, with a pixel limit against decompression bombs.
- **Rate limiting:** per-IP limit on `/analyze` (configurable with `RATE_LIMIT_PER_MINUTE`).
- **Headers:** a strict Content-Security-Policy with no inline scripts, plus `X-Frame-Options`, `X-Content-Type-Options` and `Referrer-Policy` on every response.
- **CORS and hosts:** restricted to `ALLOWED_ORIGINS` and `ALLOWED_HOSTS`; credentials are disabled.
- **Container:** runs as a non-root user on a slim base image with no compiler toolchain.

## Known limitations

- PyTorch is held at 2.6 because the published model requires fastai 2.7. Some PyTorch advisories fixed in later versions are denial-of-service issues in code paths this app doesn't use.
- Rate limits are kept in memory, so they reset on restart and aren't shared between instances.
- There's no authentication; anyone who can reach the server can use the API.
