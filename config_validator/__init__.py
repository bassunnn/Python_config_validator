"""
Пакет валидации конфигурации.

Экспортирует основную функцию validate_config и кастомные исключения.
"""

from .exceptions import (
    ConfigError,
    ConfigFileNotFoundError,
    ConfigFileReadError,
    ConfigJSONDecodeError,
    ConfigValidationError,
)
from .validator import (
    load_and_validate_config,
    validate_config,
    validate_config_dict,
)

__all__ = [
    "validate_config",
    "load_and_validate_config",
    "validate_config_dict",
    "ConfigError",
    "ConfigFileNotFoundError",
    "ConfigFileReadError",
    "ConfigJSONDecodeError",
    "ConfigValidationError",
]
