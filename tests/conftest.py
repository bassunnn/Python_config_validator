"""
Конфигурация pytest, общие фикстуры и хуки для расширенной диагностики.

Здесь собраны:
1. Фикстуры разной области видимости (scope: session, module, function)
для изоляции тестов и гибкой подготовки окружения.
2. Хуки pytest_runtest_makereport и pytest_runtest_logreport, которые перехватывают
падения тестов и логируют подробную диагностическую информацию (аргументы, время, фазу).
"""

import copy
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Generator

import pytest

test_logger = logging.getLogger("tests_diagnostics")

#ФИКСТУРЫ

@pytest.fixture(scope="session")
def base_valid_config() -> Dict[str, Any]:
    """
    Возвращает канонический шаблон валидной конфигурации из условия задачи.
    Поскольку фикстура живет всю тестовую сессию, мы используем глубокое копирование
    в тестах, чтобы никто случайно не испортил исходный эталон.
    """
    return {
        "host": "localhost",
        "port": 8080,
        "timeout": 30,
        "enabled": True,
    }


@pytest.fixture(scope="module")
def module_valid_json_file(tmp_path_factory: pytest.TempPathFactory, base_valid_config: Dict[str, Any]) -> Path:
    """
    Создает один эталонный валидный JSON-файл на весь модуль тестов.
    Полезна для тестов только на чтение (read-only), чтобы не тратить время
    на создание одинаковых файлов в каждом единичном тесте.
    """
    mod_dir = tmp_path_factory.mktemp("module_configs")
    file_path = mod_dir / "canonical_config.json"
    file_path.write_text(json.dumps(base_valid_config, indent=2), encoding="utf-8")
    return file_path


@pytest.fixture(scope="function")
def make_config_file(tmp_path: Path) -> Callable[[Any, str], Path]:
    """
    Фабричная фикстура уровня функции (scope='function').

    Обеспечивает 100% независимость и изоляцию тестов:
    каждый тест получает собственную временную папку (tmp_path),
    куда сохраняется переданный контент (словарь или сырая строка).
    """
    def _create(content: Any, filename: str = "config.json", raw: bool = False) -> Path:
        target_path = tmp_path / filename
        if raw:
            # Запись сырой строки без JSON-сериализации (для проверки синтаксических ошибок)
            target_path.write_text(str(content), encoding="utf-8")
        elif isinstance(content, bytes):
            target_path.write_bytes(content)
        else:
            # Сериализуем переданную структуру (словарь, список, примитив) в валидный JSON
            target_path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
        return target_path

    return _create


@pytest.fixture(scope="function")
def read_json_file() -> Callable[[Path], Dict[str, Any]]:
    """
    Фикстура для чтения и парсинга JSON-файла (scope='function').

    Как указано в задании:
    'Например, чтение JSON-файла может выполняться в фикстуре
    с последующей передачей полученного словаря в тест или проверяемую функцию'.
    """
    def _read(path: Path) -> Dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data

    return _read


@pytest.fixture(scope="function")
def valid_config_file(make_config_file: Callable, base_valid_config: Dict[str, Any]) -> Path:
    """
    Готовый валидный конфигурационный файл для каждого отдельного теста.
    """
    return make_config_file(copy.deepcopy(base_valid_config))


#ХУКИ

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Generator:
    """
    Хук pytest для расширенной диагностики при выполнении тестов.

    Перехватывает генерацию отчета о выполнении теста на всех этапах ('setup', 'call', 'teardown').
    Если тест падает, собирает контекст (переданные параметры, имя узла, длительность)
    и логирует расширенную диагностическую карточку ошибки.
    """
    outcome = yield
    report: pytest.TestReport = outcome.get_result()

    # Нас в первую очередь интересует фаза непосредственного выполнения теста ('call')
    if report.when == "call" and report.failed:
        # Извлекаем параметры, если тест был параметризован через @pytest.mark.parametrize
        callspec = getattr(item, "callspec", None)
        params_info = callspec.params if callspec else "нет параметров (простой тест)"

        test_logger.error(
            "\n" + "=" * 70 + "\n"
            f"[ДИАГНОСТИКА СБОЯ ТЕСТА]\n"
            f"Тест:       {item.nodeid}\n"
            f"Параметры:  {params_info}\n"
            f"Фаза:       {report.when}\n"
            f"Длительность: {report.duration:.4f} сек\n"
            f"Причина:    {call.excinfo.value if call.excinfo else 'неизвестно'}\n"
            + "=" * 70
        )


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """
    Хук для логирования промежуточных этапов выполнения тестов.
    Помогает отслеживать ход тестов в CI/CD пайплайнах Linux.
    """
    if report.passed and report.when == "call":
        test_logger.debug("Тест успешно пройден: %s (%.4fs)", report.nodeid, report.duration)
