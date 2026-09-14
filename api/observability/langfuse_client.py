"""
Centralized Langfuse observability client for DAU Buddy.

Design principles
-----------------
- **Lazy initialization**: The Langfuse client is only created when first
  needed, so importing this module has zero side-effects.
- **Graceful degradation**: If LANGFUSE_ENABLED=false, the SDK is not
  installed, or the server is unreachable, every public function here
  silently returns None or no-ops.  The chat endpoint never fails because
  of observability.
- **Privacy**: User email is hashed into a one-way ``user_id`` for
  Langfuse.  Only the email *domain* (e.g. "dau.ac.in") is stored in
  trace metadata — enough for analytics, not enough to identify a person.
- **Thread-safe**: The singleton client is created under a lock; the
  client object itself is safe to share across asyncio worker threads.
"""

import os
import hashlib
import threading
from typing import Optional

from core import config

logger = config.get_logger("api.observability")

_client = None
_lock = threading.Lock()
_initialized = False


def _is_enabled() -> bool:
    """Return True unless the operator has explicitly disabled tracing."""
    return os.getenv("LANGFUSE_ENABLED", "true").lower() in ("true", "1", "yes")


def get_langfuse():
    """Return the singleton Langfuse client, or ``None`` if disabled.
    """
    global _client, _initialized

    if not _is_enabled():
        return None
    if _initialized:
        return _client

    with _lock:
        if _initialized:
            return _client

        try:
            from langfuse import Langfuse

            host = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
            public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
            secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")

            if not public_key or not secret_key:
                logger.warning(
                    "LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY not set — "
                    "observability disabled."
                )
                _client = None
            else:
                _client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host,
                    # The SDK batches events in a background thread and
                    # flushes when the batch hits this size or this interval
                    # (seconds).  These are conservative defaults: low
                    # enough that traces appear in the dashboard within a
                    # few seconds, high enough to avoid per-event HTTP
                    # round-trips.
                    flush_at=20,
                    flush_interval=5,
                    # SDK-level errors (network, serialization) go to stderr
                    # rather than raising inside the chat request path.
                    debug=False,
                )
                logger.info(f"Langfuse observability initialized → {host}")
        except ImportError:
            logger.warning(
                "langfuse package is not installed — observability disabled. "
                "Install with: pip install langfuse"
            )
            _client = None
        except Exception as e:
            logger.warning(f"Langfuse init failed (observability disabled): {e}")
            _client = None
        finally:
            _initialized = True

    return _client



def hash_user_id(email: str) -> str:
    return "u_" + hashlib.sha256(email.encode()).hexdigest()[:16]


def flush() -> None:
    """Flush any pending Langfuse events.

    Call this on application shutdown so traces that are still in the
    SDK's in-memory buffer are not lost.  Safe to call even when
    Langfuse is disabled (no-op).
    """
    lf = get_langfuse()
    if lf is not None:
        try:
            lf.flush()
            logger.info("Langfuse buffer flushed on shutdown.")
        except Exception as e:
            logger.warning(f"Langfuse flush failed (events may be lost): {e}")
