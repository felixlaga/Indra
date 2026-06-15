"""Product API skeleton for ERLA."""

from .app import app, create_app
from .repository_factory import create_repository

__all__ = ["app", "create_app", "create_repository"]
