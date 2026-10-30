"""
Автоматизированный набор тестов для валидатора конфигурационных файлов.

Тесты полностью независимы, не зависят от глобального состояния ОС и платформы.
Покрывают:
1. Позитивные сценарии.
2. Классы эквивалентности и граничные значения для полей port и timeout.
3. Негативные сценарии.
4. Корректность и информативность кастомных исключений.
"""

import copy
from pathlib import Path
from typing import Any, Callable, Dict

import pytest

from config_validator.exceptions import (
    ConfigFileNotFoundError,
    ConfigFileReadError,
    ConfigJSONDecodeError,
    ConfigValidationError,
)
from config_validator.validator import (
    load_and_validate_config,
    validate_config,
    validate_config_dict,
)

# 1. ПОЗИТИВНЫЕ СЦЕНАРИИ

class TestPositiveScenarios:
    """Проверка корректных конфигураций и поведения."""

    def test_canonical_example_is_valid(self, valid_config_file: Path):
        assert validate_config(str(valid_config_file)) is True

    def test_module_scoped_file_is_valid(self, module_valid_json_file: Path):
        assert validate_config(str(module_valid_json_file)) is True

    @pytest.mark.parametrize(
        "port",
        [1, 2, 80, 443, 8080, 65534, 65535],
        ids=["min_port_1", "port_2", "port_80", "port_443", "port_8080", "port_65534", "max_port_65535"],
    )
    def test_valid_ports_boundary_and_typical(
        self,
        make_config_file: Callable,
        base_valid_config: Dict[str, Any],
        port: int,
    ):
        """Проверка граничных допустимых портов (1 и 65535) и типовых значений."""
        cfg = copy.deepcopy(base_valid_config)
        cfg["port"] = port
        file_path = make_config_file(cfg)
        assert validate_config(str(file_path)) is True

    @pytest.mark.parametrize(
        "timeout",
        [1, 1.0, 1.5, 30, 299.9, 300, 300.0],
        ids=[
            "min_timeout_1",
            "min_float_1.0",
            "fractional_1.5",
            "mid_30",
            "near_max_299.9",
            "max_int_300",
            "max_float_300.0",
        ],
    )
    def test_valid_timeouts_boundary_and_types(
        self,
        make_config_file: Callable,
        base_valid_config: Dict[str, Any],
        timeout: Any,
    ):
        """
        В формулировке задания сказано 'число в диапазоне от 1 до 300 включительно'.
        Числом в JSON/Python являются как целые int, так и вещественные float.
        """
        cfg = copy.deepcopy(base_valid_config)
        cfg["timeout"] = timeout
        file_path = make_config_file(cfg)
        assert validate_config(str(file_path)) is True

    @pytest.mark.parametrize("enabled", [True, False], ids=["enabled_true", "enabled_false"])
    def test_valid_enabled_boolean_values(
        self,
        make_config_file: Callable,
        base_valid_config: Dict[str, Any],
        enabled: bool,
    ):
        """Поле enabled должно поддерживать оба булевых значения: True и False."""
        cfg = copy.deepcopy(base_valid_config)
        cfg["enabled"] = enabled
        file_path = make_config_file(cfg)
        assert validate_config(str(file_path)) is True

    @pytest.mark.parametrize(
        "host",
        [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "::1",
            "kaspersky.com",
            "sub.domain.local",
            "my-server-01",
        ],
        ids=["localhost", "ipv4_loopback", "ipv4_any", "ipv6_loopback", "fqdn", "subdomain", "hyphen_name"],
    )
    def test_valid_host_variations(
        self,
        make_config_file: Callable,
        base_valid_config: Dict[str, Any],
        host: str,
    ):
        """Различные корректные форматы имен хостов и IP-адресов."""
        cfg = copy.deepcopy(base_valid_config)
        cfg["host"] = host
        file_path = make_config_file(cfg)
        assert validate_config(str(file_path)) is True

    def test_extra_fields_do_not_break_validation(
        self,
        make_config_file: Callable,
        base_valid_config: Dict[str, Any],
    ):
        """
        Наличие дополнительных опциональных полей (например, debug или metadata)
        не должно ломать валидацию, если все обязательные поля присутствуют и валидны.
        """
        cfg = copy.deepcopy(base_valid_config)
        cfg["debug"] = True
        cfg["description"] = "Test service node"
        file_path = make_config_file(cfg)
        assert validate_config(str(file_path)) is True

    def test_read_json_file_fixture_usage(
        self,
        valid_config_file: Path,
        read_json_file: Callable[[Path], Dict[str, Any]],
    ):
        """
        Проверка использования фикстуры десериализации JSON из задания:
        'чтение JSON-файла может выполняться в фикстуре с последующей передачей
        полученного словаря в тест или проверяемую функцию'.
        """
        parsed_dict = read_json_file(valid_config_file)
        assert isinstance(parsed_dict, dict)
        # Проверяем напрямую функцию валидации словаря
        validated = validate_config_dict(parsed_dict)
        assert validated["host"] == "localhost"


# 2. ФАЙЛОВЫЕ СЦЕНАРИИ И СИНТАКСИС JSON

class TestFileAndSyntaxScenarios:
    """Тестирование обработки проблем с файлами и форматом JSON."""

    def test_file_does_not_exist(self, tmp_path: Path):
        """Несуществующий файл должен возвращать False."""
        non_existent_file = tmp_path / "absent_config.json"
        assert validate_config(str(non_existent_file)) is False

        # Также проверяем, что на уровне load_and_validate_config летит понятная ошибка
        with pytest.raises(ConfigFileNotFoundError) as exc_info:
            load_and_validate_config(str(non_existent_file))
        assert "не найден" in str(exc_info.value)

    @pytest.mark.parametrize("empty_path", ["", "   ", None], ids=["empty_str", "spaces_str", "none_value"])
    def test_invalid_path_argument(self, empty_path: Any):
        """Передача пустого пути или некорректного значения."""
        assert validate_config(empty_path) is False

    def test_path_is_directory_instead_of_file(self, tmp_path: Path):
        """Если путь указывает на папку, валидатор должен корректно отработать."""
        assert validate_config(str(tmp_path)) is False
        with pytest.raises(ConfigFileReadError) as exc_info:
            load_and_validate_config(str(tmp_path))
        assert "является директорией" in str(exc_info.value)

    def test_empty_file_returns_false(self, make_config_file: Callable):
        """Пустой файл (0 байт) не является валидным JSON-файлом."""
        empty_file = make_config_file("", raw=True)
        assert validate_config(str(empty_file)) is False
        with pytest.raises(ConfigJSONDecodeError) as exc_info:
            load_and_validate_config(str(empty_file))
        assert "пуст" in str(exc_info.value).lower()

    @pytest.mark.parametrize(
        "broken_json_content",
        [
            "{'host': 'localhost'}",           # Одинарные кавычки (запрещены в JSON)
            '{"host": "localhost", "port": }', # Пропущено значение
            '{"host": "localhost"',            # Незакрытая скобка
            '{"host": "localhost",}',          # Висячая запятая (trailing comma)
            "some plain unformatted text",     # Простой текст
            "<xml><host>localhost</host></xml>", # XML вместо JSON
        ],
        ids=["single_quotes", "missing_value", "unclosed_brace", "trailing_comma", "plain_text", "xml_markup"],
    )
    def test_malformed_json_syntax(self, make_config_file: Callable, broken_json_content: str):
        """Файл с синтаксически некорректным JSON должен возвращать False."""
        broken_file = make_config_file(broken_json_content, raw=True)
        assert validate_config(str(broken_file)) is False
        with pytest.raises(ConfigJSONDecodeError):
            load_and_validate_config(str(broken_file))

    @pytest.mark.parametrize(
        "non_dict_json",
        [
            [1, 2, 3],                         # Массив чисел
            [{"host": "localhost"}],           # Массив объектов
            "just a string",                   # JSON-строка
            12345,                             # JSON-число
            True,                              # JSON-булево
            None,                              # JSON-null
        ],
        ids=["json_array", "json_array_of_objs", "json_string", "json_number", "json_bool", "json_null"],
    )
    def test_valid_json_but_not_object(self, make_config_file: Callable, non_dict_json: Any):
        """
        JSON синтаксически валиден, но корневой элемент не является словарем (JSON Object).
        Для конфигурации это недопустимо.
        """
        file_path = make_config_file(non_dict_json)
        assert validate_config(str(file_path)) is False
        with pytest.raises(ConfigValidationError) as exc_info:
            load_and_validate_config(str(file_path))
        assert exc_info.value.field == "root"

    def test_file_stat_os_error_handling(self, valid_config_file: Path, monkeypatch: pytest.MonkeyPatch):
        """Обработка системной ошибки ввода-вывода при получении метаданных файла."""
        original_stat = Path.stat

        def mock_stat(path_obj, *args, **kwargs):
            # Пробрасываем ошибку только для нашего тестового файла, чтобы не ломать pytest
            if "canonical_config" in str(path_obj) or "config.json" in str(path_obj):
                raise OSError("I/O failure on disk controller")
            return original_stat(path_obj, *args, **kwargs)

        monkeypatch.setattr(Path, "stat", mock_stat)
        assert validate_config(str(valid_config_file)) is False
        with pytest.raises(ConfigFileReadError) as exc_info:
            load_and_validate_config(str(valid_config_file))
        assert "метаданные" in str(exc_info.value)

    def test_file_read_generic_os_error_handling(self, valid_config_file: Path, monkeypatch: pytest.MonkeyPatch):
        """Обработка общей ошибки ввода-вывода при чтении файла."""
        def mock_open(*args, **kwargs):
            raise OSError("Hardware disk read error")

        monkeypatch.setattr("builtins.open", mock_open)
        assert validate_config(str(valid_config_file)) is False
        with pytest.raises(ConfigFileReadError) as exc_info:
            load_and_validate_config(str(valid_config_file))
        assert "Системная ошибка" in str(exc_info.value)

    def test_file_size_exceeds_limit(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """
        Защита от исчерпания памяти DoS.
        Проверяет, что файл, превышающий лимит размера, отклоняется до полного чтения в память.
        """
        from config_validator import validator

        monkeypatch.setattr(validator, "MAX_CONFIG_FILE_SIZE_BYTES", 100)
        oversized_file = tmp_path / "large_config.json"
        oversized_file.write_text(" " * 150, encoding="utf-8")

        assert validate_config(str(oversized_file)) is False
        with pytest.raises(ConfigFileReadError) as exc_info:
            load_and_validate_config(str(oversized_file))
        assert "превышает допустимый лимит" in str(exc_info.value)

    def test_file_with_invalid_utf8_encoding(self, make_config_file: Callable):
        """Файл содержит некорректную последовательность байтов (не UTF-8)."""
        invalid_bytes = b"\x80\x81\xFF\xFE\x00"
        corrupted_file = make_config_file(invalid_bytes)
        assert validate_config(str(corrupted_file)) is False
        with pytest.raises(ConfigFileReadError) as exc_info:
            load_and_validate_config(str(corrupted_file))
        assert "UTF-8" in str(exc_info.value)

    def test_permission_error_handling(self, valid_config_file: Path, monkeypatch: pytest.MonkeyPatch):
        """Проверка безопасной обработки ошибки отсутствия прав доступа."""
        def mock_open(*args, **kwargs):
            raise PermissionError("Access denied")

        monkeypatch.setattr("builtins.open", mock_open)
        assert validate_config(str(valid_config_file)) is False
        with pytest.raises(ConfigFileReadError) as exc_info:
            load_and_validate_config(str(valid_config_file))
        assert "прав для чтения" in str(exc_info.value)

    def test_unexpected_critical_exception_handling(self, valid_config_file: Path, monkeypatch: pytest.MonkeyPatch):
        """
        Гарантируем, что validate_config не упадет с необработанным исключением,
        даже если внутри произойдет непредвиденный сбой.
        """
        from config_validator import validator

        def mock_loader(path):
            raise RuntimeError("Unexpected memory fault or OS panic")

        monkeypatch.setattr(validator, "load_and_validate_config", mock_loader)
        assert validate_config(str(valid_config_file)) is False


# 3. ПРОВЕРКА ОТСУТСТВИЯ ОБЯЗАТЕЛЬНЫХ ПОЛЕЙ

class TestMissingRequiredFields:
    """Тестирование отсутствия любого из обязательных параметров."""

    @pytest.mark.parametrize(
        "missing_field",
        ["host", "port", "timeout", "enabled"],
        ids=["miss_host", "miss_port", "miss_timeout", "miss_enabled"],
    )
    def test_each_required_field_must_be_present(
        self,
        make_config_file: Callable,
        base_valid_config: Dict[str, Any],
        missing_field: str,
    ):
        """Удаляем поочередно каждое обязательное поле — валидация должна падать."""
        cfg = copy.deepcopy(base_valid_config)
        del cfg[missing_field]

        file_path = make_config_file(cfg)
        assert validate_config(str(file_path)) is False

        with pytest.raises(ConfigValidationError) as exc_info:
            load_and_validate_config(str(file_path))
        assert missing_field in exc_info.value.field

    def test_completely_empty_json_object(self, make_config_file: Callable):
        """Пустой JSON-объект {} не содержит ни одного обязательного поля."""
        file_path = make_config_file({})
        assert validate_config(str(file_path)) is False


# 4. ТЕСТИРОВАНИЕ ПОЛЯ 'host'

class TestHostFieldValidation:
    """Классы эквивалентности и негативные сценарии для поля host."""

    @pytest.mark.parametrize(
        "invalid_host,reason",
        [
            ("", "empty_string"),
            ("   ", "whitespace_only"),
            ("\t\n", "tabs_and_newlines"),
            (None, "none_value"),
            (127001, "integer_ip"),
            (True, "boolean_true"),
            (False, "boolean_false"),
            (["localhost"], "list_of_str"),
            ({"name": "localhost"}, "dict_object"),
        ],
        ids=[
            "empty_str",
            "spaces_only",
            "tab_newline",
            "none",
            "integer",
            "bool_true",
            "bool_false",
            "list",
            "dict",
        ],
    )
    def test_invalid_host_values(
        self,
        make_config_file: Callable,
        base_valid_config: Dict[str, Any],
        invalid_host: Any,
        reason: str,
    ):
        """Поле host не должно быть пустым или иметь нестроковый тип."""
        cfg = copy.deepcopy(base_valid_config)
        cfg["host"] = invalid_host

        file_path = make_config_file(cfg)
        assert validate_config(str(file_path)) is False

        with pytest.raises(ConfigValidationError) as exc_info:
            load_and_validate_config(str(file_path))
        assert exc_info.value.field == "host"


# 5. ТЕСТИРОВАНИЕ ПОЛЯ 'port' (ГРАНИЧНЫЕ ЗНАЧЕНИЯ И ТИПЫ)

class TestPortFieldValidation:
    """
    Классы эквивалентности и граничные значения для поля port.
    Допустимый диапазон: [1, 65535] включительно, целое число int.
    """

    @pytest.mark.parametrize(
        "out_of_range_port",
        [
            0,       # Ровно за нижней границей
            -1,      # Отрицательное значение
            -8080,   # Большое отрицательное
            65536,   # Ровно за верхней границей
            70000,   # За верхней границей
            100000,  # Заведомо недопустимый порт
        ],
        ids=["zero", "minus_one", "negative_large", "boundary_65536", "port_70000", "huge_port_100k"],
    )
    def test_port_out_of_range(
        self,
        make_config_file: Callable,
        base_valid_config: Dict[str, Any],
        out_of_range_port: int,
    ):
        """Значения вне диапазона [1, 65535] должны отклоняться."""
        cfg = copy.deepcopy(base_valid_config)
        cfg["port"] = out_of_range_port

        file_path = make_config_file(cfg)
        assert validate_config(str(file_path)) is False

        with pytest.raises(ConfigValidationError) as exc_info:
            load_and_validate_config(str(file_path))
        assert exc_info.value.field == "port"
        assert "диапазоне" in exc_info.value.message

    @pytest.mark.parametrize(
        "invalid_type_port,type_name",
        [
            (True, "bool_true"),
            (False, "bool_false"),
            (8080.0, "float_exact"),
            (8080.5, "float_fraction"),
            ("8080", "string_number"),
            ("http", "string_text"),
            (None, "none"),
            ([8080], "list"),          
            ({"port": 80}, "dict"),    
        ],
        ids=[
            "bool_true_subclass_trap",
            "bool_false_subclass_trap",
            "float_exact",
            "float_fraction",
            "string_number",
            "string_text",
            "none",
            "list",
            "dict",
        ],
    )
    def test_port_invalid_types(
        self,
        make_config_file: Callable,
        base_valid_config: Dict[str, Any],
        invalid_type_port: Any,
        type_name: str,
    ):
        cfg = copy.deepcopy(base_valid_config)
        cfg["port"] = invalid_type_port

        file_path = make_config_file(cfg)
        assert validate_config(str(file_path)) is False

        with pytest.raises(ConfigValidationError) as exc_info:
            load_and_validate_config(str(file_path))
        assert exc_info.value.field == "port"


# 6. ТЕСТИРОВАНИЕ ПОЛЯ 'timeout' (ГРАНИЧНЫЕ ЗНАЧЕНИЯ И ТИПЫ)

class TestTimeoutFieldValidation:
    """
    Классы эквивалентности и граничные значения для поля timeout.
    Допустимый диапазон: [1, 300] включительно, число int или float.
    """

    @pytest.mark.parametrize(
        "out_of_range_timeout",
        [
            0,         
            0.9999,    
            -1,        
            -0.001,    
            300.0001,  
            301,       
            500,       
        ],
        ids=[
            "zero",
            "just_below_one_0.9999",
            "minus_one",
            "negative_fractional",
            "just_above_300.0001",
            "boundary_301",
            "large_500",
        ],
    )
    def test_timeout_out_of_range(
        self,
        make_config_file: Callable,
        base_valid_config: Dict[str, Any],
        out_of_range_timeout: Any,
    ):
        """Значения вне диапазона [1, 300] отклоняются."""
        cfg = copy.deepcopy(base_valid_config)
        cfg["timeout"] = out_of_range_timeout

        file_path = make_config_file(cfg)
        assert validate_config(str(file_path)) is False

        with pytest.raises(ConfigValidationError) as exc_info:
            load_and_validate_config(str(file_path))
        assert exc_info.value.field == "timeout"

    @pytest.mark.parametrize(
        "invalid_type_timeout",
        [
            True,
            False,
            "30",
            "timeout",
            None,
            [30],
            {"sec": 30},
        ],
        ids=["bool_true", "bool_false", "string_number", "string_text", "none", "list", "dict"],
    )
    def test_timeout_invalid_types(
        self,
        make_config_file: Callable,
        base_valid_config: Dict[str, Any],
        invalid_type_timeout: Any,
    ):
        """Значения некорректных типов должны вызывать ошибку валидации."""
        cfg = copy.deepcopy(base_valid_config)
        cfg["timeout"] = invalid_type_timeout

        file_path = make_config_file(cfg)
        assert validate_config(str(file_path)) is False

        with pytest.raises(ConfigValidationError) as exc_info:
            load_and_validate_config(str(file_path))
        assert exc_info.value.field == "timeout"

    @pytest.mark.parametrize(
        "special_float",
        [float("nan"), float("inf"), float("-inf")],
        ids=["nan", "positive_infinity", "negative_infinity"],
    )
    def test_timeout_nan_and_infinity_rejected(
        self,
        base_valid_config: Dict[str, Any],
        special_float: float,
    ):
        """
        NaN и бесконечности не должны проходить.
        Проверка напрямую через валидатор словаря.
        """
        cfg = copy.deepcopy(base_valid_config)
        cfg["timeout"] = special_float
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config_dict(cfg)
        assert exc_info.value.field == "timeout"


# 7. ТЕСТИРОВАНИЕ ПОЛЯ 'enabled'

class TestEnabledFieldValidation:
    """Классы эквивалентности для булевого поля enabled."""

    @pytest.mark.parametrize(
        "non_boolean_val",
        [
            1,              # Число 1 часто путают с True
            0,              # Число 0 часто путают с False
            "true",         # Строковое представление 'true'
            "false",        # Строковое представление 'false'
            "yes",          # Строка 'yes'
            None,           # None
            [True],         # Список
            {"state": True},# Словарь
        ],
        ids=[
            "int_1_not_bool",
            "int_0_not_bool",
            "str_true",
            "str_false",
            "str_yes",
            "none",
            "list",
            "dict",
        ],
    )
    def test_enabled_must_strictly_be_boolean(
        self,
        make_config_file: Callable,
        base_valid_config: Dict[str, Any],
        non_boolean_val: Any,
    ):
        cfg = copy.deepcopy(base_valid_config)
        cfg["enabled"] = non_boolean_val

        file_path = make_config_file(cfg)
        assert validate_config(str(file_path)) is False

        with pytest.raises(ConfigValidationError) as exc_info:
            load_and_validate_config(str(file_path))
        assert exc_info.value.field == "enabled"
