"""Request-scoped context variables for telemetry enrichment.

Kept in a standalone module so both the FastAPI logging factory (in
``app.py``) and the authentication layer (in ``auth.auth_utils``) can set /
read them without introducing a circular import.
"""

from contextvars import ContextVar

conversation_id_var: ContextVar[str] = ContextVar("conversation_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")
