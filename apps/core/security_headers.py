"""
Security Headers Middleware для Django.

Этот модуль предоставляет middleware для добавления security headers
для защиты от XSS, clickjacking и других атак.
"""

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.http import HttpRequest, HttpResponse

if TYPE_CHECKING:
    pass

logger = logging.getLogger("security_headers")


class SecurityHeadersMiddleware:
    """
    Middleware для добавления security headers к HTTP-ответам.

    Добавляет следующие headers:
    - Content-Security-Policy (CSP)
    - HTTP Strict Transport Security (HSTS)
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Referrer-Policy
    - Permissions-Policy
    """

    def __init__(self, get_response):
        """
        Инициализирует middleware.

        PARAMETERS:
          get_response: Callable - Следующий middleware или view в цепочке
        """
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Обрабатывает запрос и добавляет security headers к ответу.

        PARAMETERS:
          request: HttpRequest - Входящий HTTP запрос

        RETURNS:
          HttpResponse - HTTP ответ с добавленными security headers

        GUARANTEES:
          - Если SECURITY_HEADERS_ENABLED=False, возвращает ответ без изменений
          - В development mode (DEBUG=True) HSTS отключен
          - Все security headers логируются на уровне DEBUG
        """
        response = self.get_response(request)

        # Проверяем, включены ли security headers
        if not getattr(settings, "SECURITY_HEADERS_ENABLED", True):
            return response

        # Добавляем Content Security Policy
        self._add_csp_headers(response)

        # Добавляем HSTS (только в production)
        self._add_hsts_headers(response)

        # Добавляем X-Content-Type-Options
        self._add_content_type_options(response)

        # Добавляем X-Frame-Options
        self._add_frame_options(response)

        # Добавляем X-XSS-Protection
        self._add_xss_protection(response)

        # Добавляем Referrer-Policy
        self._add_referrer_policy(response)

        # Добавляем Permissions-Policy
        self._add_permissions_policy(response)

        return response

    def _add_csp_headers(self, response: HttpResponse) -> None:
        """
        Добавляет Content Security Policy headers к ответу.

        PARAMETERS:
          response: HttpResponse - HTTP ответ для модификации

        GUARANTEES:
          - Если CSP_ENABLED=False, header не добавляется
          - CSP header формируется из настроек в settings.py
          - Header логируется на уровне DEBUG
        """
        if not getattr(settings, "CSP_ENABLED", True):
            return

        csp_parts = []

        # Собираем CSP директивы из настроек
        directives = [
            ("default-src", getattr(settings, "CSP_DEFAULT_SRC", "'self'")),
            ("script-src", getattr(settings, "CSP_SCRIPT_SRC", "'self' 'unsafe-inline' 'unsafe-eval'")),
            ("style-src", getattr(settings, "CSP_STYLE_SRC", "'self' 'unsafe-inline'")),
            ("img-src", getattr(settings, "CSP_IMG_SRC", "'self' data: https:")),
            ("connect-src", getattr(settings, "CSP_CONNECT_SRC", "'self'")),
            ("font-src", getattr(settings, "CSP_FONT_SRC", "'self'")),
            ("object-src", getattr(settings, "CSP_OBJECT_SRC", "'none'")),
            ("media-src", getattr(settings, "CSP_MEDIA_SRC", "'self'")),
            ("frame-src", getattr(settings, "CSP_FRAME_SRC", "'none'")),
            ("base-uri", getattr(settings, "CSP_BASE_URI", "'self'")),
            ("form-action", getattr(settings, "CSP_FORM_ACTION", "'self'")),
        ]

        for directive, value in directives:
            if value:
                csp_parts.append(f"{directive} {value}")

        csp_value = "; ".join(csp_parts)

        if csp_value:
            response["Content-Security-Policy"] = csp_value
            logger.debug(f"Added CSP header: {csp_value}")

    def _add_hsts_headers(self, response: HttpResponse) -> None:
        """
        Добавляет HTTP Strict Transport Security headers к ответу.

        PARAMETERS:
          response: HttpResponse - HTTP ответ для модификации

        GUARANTEES:
          - Если HSTS_ENABLED=False или DEBUG=True, header не добавляется
          - HSTS header включает max-age, includeSubDomains и preload если настроено
          - Header логируется на уровне DEBUG
        """
        # HSTS не должен быть включен в development mode
        if getattr(settings, "DEBUG", False):
            return

        if not getattr(settings, "HSTS_ENABLED", True):
            return

        max_age = getattr(settings, "HSTS_MAX_AGE", 31536000)
        include_subdomains = getattr(settings, "HSTS_INCLUDE_SUBDOMAINS", True)
        preload = getattr(settings, "HSTS_PRELOAD", True)

        hsts_parts = [f"max-age={max_age}"]

        if include_subdomains:
            hsts_parts.append("includeSubDomains")

        if preload:
            hsts_parts.append("preload")

        hsts_value = "; ".join(hsts_parts)
        response["Strict-Transport-Security"] = hsts_value
        logger.debug(f"Added HSTS header: {hsts_value}")

    def _add_content_type_options(self, response: HttpResponse) -> None:
        """
        Добавляет X-Content-Type-Options header к ответу.

        PARAMETERS:
          response: HttpResponse - HTTP ответ для модификации

        GUARANTEES:
          - Header устанавливается в 'nosniff' если настроено
          - Header логируется на уровне DEBUG
        """
        value = getattr(settings, "X_CONTENT_TYPE_OPTIONS", "nosniff")
        if value:
            response["X-Content-Type-Options"] = value
            logger.debug(f"Added X-Content-Type-Options header: {value}")

    def _add_frame_options(self, response: HttpResponse) -> None:
        """
        Добавляет X-Frame-Options header к ответу.

        PARAMETERS:
          response: HttpResponse - HTTP ответ для модификации

        GUARANTEES:
          - Header устанавливается из настроек (DENY, SAMEORIGIN или ALLOW-FROM)
          - Header логируется на уровне DEBUG
        """
        value = getattr(settings, "X_FRAME_OPTIONS", "DENY")
        if value:
            response["X-Frame-Options"] = value
            logger.debug(f"Added X-Frame-Options header: {value}")

    def _add_xss_protection(self, response: HttpResponse) -> None:
        """
        Добавляет X-XSS-Protection header к ответу.

        PARAMETERS:
          response: HttpResponse - HTTP ответ для модификации

        GUARANTEES:
          - Header устанавливается из настроек (обычно '1; mode=block')
          - Header логируется на уровне DEBUG
        """
        value = getattr(settings, "X_XSS_PROTECTION", "1; mode=block")
        if value:
            response["X-XSS-Protection"] = value
            logger.debug(f"Added X-XSS-Protection header: {value}")

    def _add_referrer_policy(self, response: HttpResponse) -> None:
        """
        Добавляет Referrer-Policy header к ответу.

        PARAMETERS:
          response: HttpResponse - HTTP ответ для модификации

        GUARANTEES:
          - Header устанавливается из настроек
          - Header логируется на уровне DEBUG
        """
        value = getattr(settings, "REFERRER_POLICY", "strict-origin-when-cross-origin")
        if value:
            response["Referrer-Policy"] = value
            logger.debug(f"Added Referrer-Policy header: {value}")

    def _add_permissions_policy(self, response: HttpResponse) -> None:
        """
        Добавляет Permissions-Policy (ранее Feature-Policy) header к ответу.

        PARAMETERS:
          response: HttpResponse - HTTP ответ для модификации

        GUARANTEES:
          - Header устанавливается из настроек PERMISSIONS_POLICY
          - Если PERMISSIONS_POLICY не задан, используется дефолтная политика
          - Header логируется на уровне DEBUG
        """
        # Дефолтная политика: отключаем геолокацию, камеру, микрофон
        default_policy = "geolocation=(), camera=(), microphone=()"
        value = getattr(settings, "PERMISSIONS_POLICY", default_policy)

        if value:
            response["Permissions-Policy"] = value
            logger.debug(f"Added Permissions-Policy header: {value}")
