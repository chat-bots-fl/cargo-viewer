"""
Модуль мониторинга и алертинга с интеграцией Sentry.

Обеспечивает отслеживание ошибок, производительности и пользовательских сессий
в реальном времени с возможностью graceful degradation при недоступности Sentry.
"""

from typing import Optional, Dict, Any
from sentry_sdk import init as sentry_init, capture_exception as sentry_capture_exception
from sentry_sdk import capture_message as sentry_capture_message, set_user as sentry_set_user
from sentry_sdk import add_breadcrumb as sentry_add_breadcrumb, start_transaction as sentry_start_transaction
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration
import logging

logger = logging.getLogger(__name__)

# Глобальный флаг для отключения Sentry (например, в тестах)
_sentry_enabled: bool = False


"""
GOAL: Инициализировать Sentry SDK для мониторинга ошибок и производительности.

PARAMETERS:
  dsn: str - Sentry DSN (Data Source Name) - Пустая строка отключает мониторинг
  environment: str - Окружение (development, staging, production) - Не пустое
  traces_sample_rate: float - Частота сбора трассировок (0.0-1.0) - 0.0 <= value <= 1.0
  profiles_sample_rate: float - Частота профилирования (0.0-1.0) - 0.0 <= value <= 1.0
  release: Optional[str] - Версия релиза - Может быть None
  server_name: Optional[str] - Имя сервера - Может быть None

RETURNS:
  bool - True если Sentry инициализирован, False если отключен - Никогда не вызывает исключения

RAISES:
  None - Функция никогда не вызывает исключений (graceful degradation)

GUARANTEES:
  - При пустом DSN возвращает False и не инициализирует Sentry
  - При успешной инициализации возвращает True
  - При ошибке инициализации логирует ошибку и возвращает False
  - Глобальный флаг _sentry_enabled соответствует фактическому состоянию
"""
def init_sentry(
    dsn: str,
    environment: str = "development",
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.1,
    release: Optional[str] = None,
    server_name: Optional[str] = None
) -> bool:
    """
    Инициализировать Sentry SDK с интеграциями Django, Logging и Redis.
    При пустом DSN или ошибке инициализации отключает мониторинг без сбоя приложения.
    """
    global _sentry_enabled
    
    # Отключаем мониторинг если DSN не указан
    if not dsn or dsn.strip() == "":
        logger.info("Sentry monitoring disabled: SENTRY_DSN is empty")
        _sentry_enabled = False
        return False
    
    try:
        sentry_init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,
            release=release,
            server_name=server_name,
            integrations=[
                DjangoIntegration(),
                LoggingIntegration(
                    level=logging.INFO,  # Capture info and above as breadcrumbs
                    event_level=logging.ERROR  # Send errors as events
                ),
                RedisIntegration(),
            ],
            # Игнорировать некоторые типы исключений
            ignore_errors=[
                KeyboardInterrupt,
                SystemExit,
            ],
            # Перед отправкой события можно модифицировать или отфильтровать
            before_send=_before_send_event,
            before_send_transaction=_before_send_transaction,
        )
        
        _sentry_enabled = True
        logger.info(f"Sentry monitoring initialized: environment={environment}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}", exc_info=True)
        _sentry_enabled = False
        return False


"""
GOAL: Отправить исключение в Sentry для мониторинга и анализа.

PARAMETERS:
  exception: Exception - Исключение для отправки - Не None
  level: Optional[str] - Уровень логирования - 'error', 'warning', 'info'
  extra: Optional[Dict[str, Any]] - Дополнительные данные контекста - Может быть None
  tags: Optional[Dict[str, str]] - Теги для группировки событий - Может быть None

RETURNS:
  Optional[str] - ID события в Sentry или None если Sentry отключен - Может быть None

RAISES:
  None - Функция никогда не вызывает исключений (graceful degradation)

GUARANTEES:
  - При отключенном Sentry возвращает None без ошибок
  - При успешной отправке возвращает ID события
  - Дополнительные данные и теги добавляются к событию
  - Ошибки отправки логируются локально
"""
def capture_exception(
    exception: Exception,
    level: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    tags: Optional[Dict[str, str]] = None
) -> Optional[str]:
    """
    Отправить исключение в Sentry с дополнительным контекстом.
    Если Sentry отключен, просто логирует ошибку локально.
    """
    if not _sentry_enabled:
        logger.error(f"Exception (Sentry disabled): {type(exception).__name__}: {exception}")
        return None
    
    try:
        # Добавляем дополнительный контекст
        with sentry_configure_scope() as scope:
            if extra:
                scope.set_context("extra", extra)
            if tags:
                for key, value in tags.items():
                    scope.set_tag(key, value)
            if level:
                scope.set_level(level)
        
        event_id = sentry_capture_exception(exception)
        logger.info(f"Exception sent to Sentry: {event_id}")
        return event_id
        
    except Exception as e:
        logger.error(f"Failed to send exception to Sentry: {e}", exc_info=True)
        return None


"""
GOAL: Отправить сообщение в Sentry для мониторинга и анализа.

PARAMETERS:
  message: str - Сообщение для отправки - Не пустое
  level: str - Уровень важности - 'debug', 'info', 'warning', 'error', 'fatal'
  extra: Optional[Dict[str, Any]] - Дополнительные данные контекста - Может быть None
  tags: Optional[Dict[str, str]] - Теги для группировки событий - Может быть None

RETURNS:
  Optional[str] - ID события в Sentry или None если Sentry отключен - Может быть None

RAISES:
  None - Функция никогда не вызывает исключений (graceful degradation)

GUARANTEES:
  - При отключенном Sentry возвращает None без ошибок
  - При успешной отправке возвращает ID события
  - Сообщение логируется локально на соответствующем уровне
  - Дополнительные данные и теги добавляются к событию
"""
def capture_message(
    message: str,
    level: str = "info",
    extra: Optional[Dict[str, Any]] = None,
    tags: Optional[Dict[str, str]] = None
) -> Optional[str]:
    """
    Отправить сообщение в Sentry с дополнительным контекстом.
    Используется для отслеживания бизнес-событий и предупреждений.
    """
    if not _sentry_enabled:
        # Логируем локально на соответствующем уровне
        log_level = getattr(logging, level.upper(), logging.INFO)
        logger.log(log_level, f"Message (Sentry disabled): {message}")
        return None
    
    try:
        # Добавляем дополнительный контекст
        with sentry_configure_scope() as scope:
            if extra:
                scope.set_context("extra", extra)
            if tags:
                for key, value in tags.items():
                    scope.set_tag(key, value)
        
        event_id = sentry_capture_message(message, level=level)
        logger.info(f"Message sent to Sentry: {event_id}")
        return event_id
        
    except Exception as e:
        logger.error(f"Failed to send message to Sentry: {e}", exc_info=True)
        return None


"""
GOAL: Установить контекст пользователя для всех последующих событий в текущей сессии.

PARAMETERS:
  user_id: Optional[int] - ID пользователя - Может быть None для анонимных
  username: Optional[str] - Имя пользователя - Может быть None
  email: Optional[str] - Email пользователя - Может быть None
  ip_address: Optional[str] - IP адрес пользователя - Может быть None
  extra: Optional[Dict[str, Any]] - Дополнительные данные пользователя - Может быть None

RETURNS:
  None - Функция ничего не возвращает

RAISES:
  None - Функция никогда не вызывает исключений (graceful degradation)

GUARANTEES:
  - При отключенном Sentry ничего не делает
  - Контекст пользователя применяется ко всем последующим событиям
  - Все параметры являются опциональными
  - Дополнительные данные добавляются в контекст пользователя
"""
def set_user_context(
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    email: Optional[str] = None,
    ip_address: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None
) -> None:
    """
    Установить контекст пользователя для трассировки действий.
    Все последующие события будут связаны с этим пользователем.
    """
    if not _sentry_enabled:
        return
    
    try:
        user_data: Dict[str, Any] = {}
        
        if user_id is not None:
            user_data["id"] = str(user_id)
        if username is not None:
            user_data["username"] = username
        if email is not None:
            user_data["email"] = email
        if ip_address is not None:
            user_data["ip_address"] = ip_address
        if extra is not None:
            user_data.update(extra)
        
        # Если есть хотя бы один параметр, устанавливаем контекст
        if user_data:
            sentry_set_user(user_data)
        
    except Exception as e:
        logger.error(f"Failed to set user context: {e}", exc_info=True)


"""
GOAL: Начать транзакцию для отслеживания производительности операции.

PARAMETERS:
  name: str - Имя транзакции - Не пустое
  op: str - Тип операции - Не пустое
  tags: Optional[Dict[str, str]] - Теги для группировки - Может быть None

RETURNS:
  Any - Объект транзакции или None если Sentry отключен - Может быть None

RAISES:
  None - Функция никогда не вызывает исключений (graceful degradation)

GUARANTEES:
  - При отключенном Sentry возвращает None без ошибок
  - Возвращенный объект можно использовать как контекстный менеджер
  - Теги добавляются к транзакции
  - Транзакция автоматически завершается при выходе из контекста
"""
def set_transaction(
    name: str,
    op: str,
    tags: Optional[Dict[str, str]] = None
) -> Any:
    """
    Начать транзакцию для мониторинга производительности.
    Используется как контекстный менеджер: with set_transaction(...) as transaction:
    """
    if not _sentry_enabled:
        return None
    
    try:
        transaction = sentry_start_transaction(name=name, op=op)
        
        if tags:
            for key, value in tags.items():
                transaction.set_tag(key, value)
        
        return transaction
        
    except Exception as e:
        logger.error(f"Failed to start transaction: {e}", exc_info=True)
        return None


"""
GOAL: Добавить breadcrumb (хлебную крошку) для контекста событий.

PARAMETERS:
  message: str - Сообщение breadcrumb - Не пустое
  category: str - Категория breadcrumb - Не пустая
  level: str - Уровень важности - 'debug', 'info', 'warning', 'error'
  data: Optional[Dict[str, Any]] - Дополнительные данные - Может быть None
  type: Optional[str] - Тип breadcrumb - Может быть None

RETURNS:
  None - Функция ничего не возвращает

RAISES:
  None - Функция никогда не вызывает исключений (graceful degradation)

GUARANTEES:
  - При отключенном Sentry ничего не делает
  - Breadcrumb добавляется к текущей сессии
  - Breadcrumb отображается в контексте последующих событий
  - Дополнительные данные добавляются в breadcrumb
"""
def add_breadcrumb(
    message: str,
    category: str = "default",
    level: str = "info",
    data: Optional[Dict[str, Any]] = None,
    type: Optional[str] = None
) -> None:
    """
    Добавить breadcrumb для отслеживания последовательности действий.
    Breadcrumb помогает понять контекст возникновения ошибки.
    """
    if not _sentry_enabled:
        return
    
    try:
        breadcrumb_data: Dict[str, Any] = {
            "message": message,
            "category": category,
            "level": level,
        }
        
        if data:
            breadcrumb_data["data"] = data
        if type:
            breadcrumb_data["type"] = type
        
        sentry_add_breadcrumb(breadcrumb_data)
        
    except Exception as e:
        logger.error(f"Failed to add breadcrumb: {e}", exc_info=True)


"""
GOAL: Проверить, включен ли мониторинг Sentry.

PARAMETERS:
  None

RETURNS:
  bool - True если Sentry включен, False если отключен - Никогда не вызывает исключения

RAISES:
  None - Функция никогда не вызывает исключений

GUARANTEES:
  - Возвращает актуальное состояние мониторинга
  - Результат соответствует глобальному флагу _sentry_enabled
"""
def is_sentry_enabled() -> bool:
    """
    Проверить статус мониторинга Sentry.
    Используется для условного выполнения кода мониторинга.
    """
    return _sentry_enabled


# Вспомогательные функции

def _before_send_event(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Модифицировать или отфильтровать событие перед отправкой в Sentry.
    """
    # Можно добавить логику фильтрации или модификации событий
    # Например, исключить события из тестов
    return event


def _before_send_transaction(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Модифицировать или отфильтровать транзакцию перед отправкой в Sentry.
    """
    # Можно добавить логику фильтрации транзакций
    return event


# Импорт configure_scope из sentry_sdk для использования в функциях
try:
    from sentry_sdk import configure_scope as sentry_configure_scope
except ImportError:
    # Fallback если sentry_sdk не установлен
    def sentry_configure_scope():
        """
        Заглушка для configure_scope если sentry_sdk не установлен.
        """
        class DummyScope:
            def set_context(self, name, data):
                pass
            def set_tag(self, key, value):
                pass
            def set_level(self, level):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        return DummyScope()
