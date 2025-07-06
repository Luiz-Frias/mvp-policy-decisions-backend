"""API middleware for authentication and request processing."""

from .oauth2_middleware import OAuth2Middleware

__all__ = ["OAuth2Middleware"]
