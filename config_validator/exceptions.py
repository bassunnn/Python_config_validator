"""
Пользовательские исключения для валидатора конфигурационных файлов.

Ошибки валидации вносятся в отдельную иерархию, по двум основным причинам:
1. Иметь возможность отлавливать именно конфигурационные сбои, не трогая системные ошибки.
2. Предоставлять вызывающему коду детальную диагностику т.е сообщать какое конкретно поле сломано,
   какое значение пришло и почему оно не прошло проверку.
"""

from typing import Any


class ConfigError(Exception):
    """Базовый класс для всех ошибок, связанных с конфигурацией."""
    pass


class ConfigFileNotFoundError(ConfigError):
    """Вызывается, когда файл конфигурации отсутствует по указанному пути."""
    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Конфигурационный файл не найден по пути: '{path}'")


class ConfigFileReadError(ConfigError):
    """
    Вызывается при проблемах с чтением файла.
    """
    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"Не удалось прочитать файл '{path}': {reason}")


class ConfigJSONDecodeError(ConfigError):
    """
    Вызывается, если файл содержит некорректный JSON
    или если корневой элемент JSON не является объектом/словарем.
    """
    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"Ошибка разбора JSON в файле '{path}': {reason}")


class ConfigValidationError(ConfigError):
    """
    Вызывается при нарушении бизнес-правил конфигурации.
    Отсутствие обязательного поля, неверный тип данных или выход за границы диапазона.
    """
    def __init__(self, field: str, value: Any, message: str):
        self.field = field
        self.value = value
        self.message = message
        super().__init__(f"Ошибка валидации поля '{field}' (значение: {repr(value)}): {message}")
