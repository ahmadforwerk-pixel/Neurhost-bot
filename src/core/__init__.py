"""Core module initialization."""

try:
    from src.core.config import Config, Constants
    __all__ = ["Config", "Constants"]
except ValueError:
    # Config requires environment variables - that's OK for testing
    __all__ = []
    Config = None
    Constants = None
