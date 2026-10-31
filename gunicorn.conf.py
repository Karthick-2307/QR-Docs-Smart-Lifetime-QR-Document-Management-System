# Gunicorn Production Configuration for QR Docs
import multiprocessing
import os

bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"

# 2-3 workers recommended for SQLite with WAL mode
workers = int(os.getenv("GUNICORN_WORKERS", "3"))
worker_class = "sync"
worker_connections = 1000
timeout = 60
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Security & Limits
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

def on_starting(server):
    server.log.info("Starting QR Docs production Gunicorn server with SQLite WAL mode support...")

