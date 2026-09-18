# Nginx entrypoint

The runnable Nginx configuration is kept at `frontend/nginx.conf` because the frontend image builds the Vue application and serves it from the same gateway container. It also proxies `/api/` to FastAPI and sets basic browser security headers.

