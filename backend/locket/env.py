"""Environment bootstrap module for Locket.

Ensures .env is loaded as early as possible before any configuration or auth
constants are evaluated and frozen.
"""

import os
import dotenv

# Load .env into os.environ if not already loaded (does not overwrite existing vars by default)
dotenv.load_dotenv()


def init_env(override: bool = False):
    """Explicitly initialize or reload environment variables from .env."""
    dotenv.load_dotenv(override=override)


def get_env_var(key: str, default: str = None) -> str:
    """Read an environment variable dynamically."""
    return os.getenv(key, default)
