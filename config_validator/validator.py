"""
Модуль валидации конфигурационного JSON-файла.

Реализует проверку структуры, обязательных параметров, типов и диапазонов значений
в соответствии с требованиями тестового задания.
"""

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict

from .exceptions import (
    ConfigError,
    ConfigFileNotFoundError,
    ConfigFileReadError,
    ConfigJSONDecodeError,
    ConfigValidationError,
)


logger = logging.getLogger("config_validator")

MAX_CONFIG_FILE_SIZE_BYTES = 10 * 1024 * 1024

REQUIRED_FIELDS = {"host", "port", "timeout", "enabled"}


def validate_config_dict(data: Any) -> Dict[str, Any]:
    """
    Валидирует уже распарсенную структуру данных конфигурации.

    Выбрасывает ConfigValidationError с подробным описанием причины,
    если хоть одно поле не соответствует спецификации.
    """

    if not isinstance(data, dict):
        raise ConfigValidationError(
            field="root",
            value=type(data).__name__,
            message="Корневым элементом JSON должен быть объект (dict), а не примитив или список",
        )

    missing_fields = REQUIRED_FIELDS - data.keys()
    if missing_fields:
        missing_str = ", ".join(sorted(missing_fields))
        raise ConfigValidationError(
            field=missing_str,
            value=None,
            message=f"Отсутствуют обязательные поля: {missing_str}",
        )

    host = data["host"]
    if not isinstance(host, str):
        raise ConfigValidationError(
            field="host",
            value=host,
            message=f"Поле должно быть строкой (получен {type(host).__name__})",
        )

    if not host.strip():
        raise ConfigValidationError(
            field="host",
            value=host,
            message="Поле не может быть пустой строкой или содержать только пробелы",
        )

    port = data["port"]
    # Важный нюанс python: тип bool является прямым подклассом int.
    # То есть обычная проверка isinstance(True, int) вернет True.
    # Если не исключить bool явно, port: true посчитается валидным портом 1.
    if isinstance(port, bool) or not isinstance(port, int):
        raise ConfigValidationError(
            field="port",
            value=port,
            message=f"Поле должно быть целым числом int (получен {type(port).__name__})",
        )
    if not (1 <= port <= 65535):
        raise ConfigValidationError(
            field="port",
            value=port,
            message=f"Значение порта должно быть в диапазоне от 1 до 65535 включительно (получено: {port})",
        )

    timeout = data["timeout"]

    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise ConfigValidationError(
            field="timeout",
            value=timeout,
            message=f"Поле должно быть числом (int или float, получен {type(timeout).__name__})",
        )
    
    if math.isnan(timeout) or math.isinf(timeout):
        raise ConfigValidationError(
            field="timeout",
            value=timeout,
            message="Значение timeout не может быть NaN или бесконечностью",
        )
    if not (1 <= timeout <= 300):
        raise ConfigValidationError(
            field="timeout",
            value=timeout,
            message=f"Значение timeout должно быть в диапазоне от 1 до 300 включительно (получено: {timeout})",
        )

    enabled = data["enabled"]

    if not isinstance(enabled, bool):
        raise ConfigValidationError(
            field="enabled",
            value=enabled,
            message=f"Поле должно быть булевым значением (bool, получен {type(enabled).__name__})",
        )

    return data


def load_and_validate_config(path: str) -> Dict[str, Any]:
    """
    Загружает конфигурационный файл с диска и выполняет его полную валидацию.

    Выбрасывает соответствующие подклассы ConfigError в случае любых проблем.
    Используется в сценариях, где вызывающему коду важно точно знать причину ошибки.
    """
    if not isinstance(path, (str, Path)) or not str(path).strip():
        raise ConfigFileNotFoundError(str(path))

    file_path = Path(path)

    try:
        if not file_path.exists():
            raise ConfigFileNotFoundError(str(file_path))

        if file_path.is_dir():
            raise ConfigFileReadError(str(file_path), "Указанный путь является директорией, а не файлом")

        file_size = file_path.stat().st_size
    except ConfigError:
        raise
    except OSError as err:
        raise ConfigFileReadError(str(file_path), f"Не удалось получить метаданные файла: {err}") from err

    if file_size > MAX_CONFIG_FILE_SIZE_BYTES:
        raise ConfigFileReadError(
            str(file_path),
            f"Размер файла ({file_size} байт) превышает допустимый лимит ({MAX_CONFIG_FILE_SIZE_BYTES} байт)",
        )

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except PermissionError as err:
        raise ConfigFileReadError(str(file_path), "Отказано в доступе (недостаточно прав для чтения файла)") from err
    except UnicodeDecodeError as err:
        raise ConfigFileReadError(str(file_path), f"Файл не является корректным UTF-8 текстом: {err}") from err
    except OSError as err:
        raise ConfigFileReadError(str(file_path), f"Системная ошибка ввода-вывода при чтении: {err}") from err

    if not content.strip():
        raise ConfigJSONDecodeError(str(file_path), "Файл пуст")

    try:
        parsed_json = json.loads(content)
    except json.JSONDecodeError as err:
        raise ConfigJSONDecodeError(
            str(file_path),
            f"Некорректный синтаксис JSON на строке {err.lineno}, позиции {err.colno}: {err.msg}",
        ) from err

    return validate_config_dict(parsed_json)


def validate_config(path: str) -> bool:
    """
    Основная функция проверки конфигурационного файла по требованиям задания.

    Возвращает True, если конфигурация корректна, и False при любых ошибках.
    При возникновении ошибок фиксирует диагностику в лог.
    """
    try:
        load_and_validate_config(path)
        logger.info("Конфигурационный файл '%s' успешно прошел валидацию", path)
        return True
    except ConfigError as err:
        logger.warning("Валидация файла '%s' завершилась неудачей: %s", path, err)
        return False
    except Exception as unexpected_err:
        logger.error(
            "Непредвиденная критическая ошибка при проверке конфига '%s': %s",
            path,
            unexpected_err,
            exc_info=True,
        )
        return False
