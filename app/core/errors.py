"""Custom exception hierarchy for the SMU Data App."""


class AppError(Exception):
    """Base class for all application errors."""


class ConfigError(AppError):
    """A required configuration value is missing or invalid."""


class DataLoadError(AppError):
    """Failed to load, parse, or validate a dataset."""


class GeoError(AppError):
    """An error related to geographic data or lookups."""


class APIError(AppError):
    """An upstream API returned an unexpected status or payload."""


class LLMError(AppError):
    """An error occurred while interacting with the LLM backend."""


class ValidationError(AppError):
    """User-supplied input failed validation."""


class CodeExecutionError(AppError):
    """LLM-generated code failed safety checks or execution."""
