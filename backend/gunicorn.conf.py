"""Gunicorn config for production VPS deployment.

The QueueManager spawns one daemon thread per Locket account at import time.
That means we MUST run a single gunicorn worker process — multiple processes
would each spawn their own thread pool, all polling the same SQLite queue,
and you'd have N × workers threads for no extra throughput. Concurrency for
HTTP requests is handled by `threads` instead.
"""

import multiprocessing  # noqa: F401  (kept so users grep'ing for it find this comment)

# Listen only on loopback — nginx terminates TLS and proxies to us.
bind = "127.0.0.1:5001"

# One process. Required for singleton QueueManager and SQLite concurrency.
workers = 1

# Threads inside the single worker process.
# On a 2 CPU / 2GB RAM VPS, 4 threads provide excellent concurrency for lightweight
# I/O requests while keeping memory footprint strictly under ~120MB, leaving ample RAM
# for Ubuntu OS, systemd, Nginx, and page cache.
threads = 4
worker_class = "gthread"

# Gunicorn 25.1+ starts a control socket (for `gunicornc`). Its default path is
# $XDG_RUNTIME_DIR/gunicorn.ctl, else $HOME/.gunicorn/gunicorn.ctl — under systemd
# that resolves to /opt/locket-gold/.gunicorn, which is read-only
# (ProtectSystem=strict). Keep it in the writable runtime dir instead.
# (This is separate from worker_tmp_dir below.)
control_socket = "/run/locket-gold/gunicorn.ctl"

# Per-worker heartbeat temp files. Point them at the same writable runtime dir
# so nothing under the read-only source tree is touched.
worker_tmp_dir = "/run/locket-gold"

# Restore work runs out-of-band, so HTTP timeouts only need to cover
# /api/get-user-info (synchronous) and admin pages.
timeout = 60
graceful_timeout = 30

# preload_app=False (default) is REQUIRED. With preload, the master imports
# wsgi.py — which calls create_app() and spawns QueueManager daemon threads —
# and then forks. Threads do not survive fork(), so the daemon would silently die.
preload_app = False

# Send access + error logs to stdout/stderr; systemd journald captures them.
accesslog = "-"
errorlog = "-"
loglevel = "info"
