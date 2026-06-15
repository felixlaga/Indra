"""Product API skeleton for ERLA.

Package-level exports are lazy so importing schema or mapping modules does not
require FastAPI to be installed or initialize an app.
"""

__all__ = ["app", "create_app", "create_repository"]


def __getattr__(name: str):
    if name in {"app", "create_app"}:
        from .app import app, create_app

        return {"app": app, "create_app": create_app}[name]
    if name == "create_repository":
        from .repository_factory import create_repository

        return create_repository
    raise AttributeError(f"module 'src.api' has no attribute {name!r}")
