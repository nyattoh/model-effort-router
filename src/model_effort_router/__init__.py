"""Provider-neutral task decomposition and model/effort routing."""

from .router import RouterError, route, validate_request

__all__ = ["RouterError", "route", "validate_request"]
__version__ = "0.1.0"
