"""Server-side activation provider clients.

Each provider lives in its own module and exposes a small, mockable client.
Provider modules must never perform network I/O at import time and must read
credentials exclusively from the backend environment.
"""
