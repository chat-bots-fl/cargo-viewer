# Security Headers Documentation

## Обзор

В проекте `cargo-viewer` реализован middleware для добавления security headers к HTTP-ответам. Security headers - это важный слой защиты от различных веб-атак, таких как XSS, clickjacking, MITM и другие.

## Реализация

### Middleware

**Файл:** [`apps/core/security_headers.py`](../apps/core/security_headers.py)

**Класс:** `SecurityHeadersMiddleware`

Middleware автоматически добавляет следующие security headers ко всем HTTP-ответам:

1. Content-Security-Policy (CSP)
2. HTTP Strict Transport Security (HSTS)
3. X-Content-Type-Options
4. X-Frame-Options
5. X-XSS-Protection
6. Referrer-Policy
7. Permissions-Policy

## Security Headers

### 1. Content Security Policy (CSP)

**Header:** `Content-Security-Policy`

**Цель:** Защита от XSS-атак и инъекций данных.

**Как работает:** CSP ограничивает источники, с которых браузер может загружать ресурсы (скрипты, стили, изображения, шрифты и т.д.).

**Предотвращаемые атаки:**
- Cross-Site Scripting (XSS)
- Data injection attacks
- Clickjacking (частично)

**Настройки в settings.py:**

```python
# Включение/выключение CSP
CSP_ENABLED = True

# Директивы CSP
CSP_DEFAULT_SRC = "'self'"  # Источники по умолчанию
CSP_SCRIPT_SRC = "'self' 'unsafe-inline' 'unsafe-eval'"  # Скрипты
CSP_STYLE_SRC = "'self' 'unsafe-inline'"  # Стили
CSP_IMG_SRC = "'self' data: https:"  # Изображения
CSP_CONNECT_SRC = "'self'"  # AJAX/WebSocket соединения
CSP_FONT_SRC = "'self'"  # Шрифты
CSP_OBJECT_SRC = "'none'"  # Объекты (Flash, плагины)
CSP_MEDIA_SRC = "'self'"  # Аудио/видео
CSP_FRAME_SRC = "'none'"  # Фреймы
CSP_BASE_URI = "'self'"  # Базовый URL
CSP_FORM_ACTION = "'self'"  # URL для отправки форм
```

**Пример значения CSP:**

```
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self'; font-src 'self'; object-src 'none'; media-src 'self'; frame-src 'none'; base-uri 'self'; form-action 'self'
```

**Рекомендации:**

1. **Избегайте `'unsafe-inline'` и `'unsafe-eval'`** в production, если возможно
2. **Используйте nonce или hash** для inline скриптов вместо `'unsafe-inline'`
3. **Ограничьте `img-src`** только необходимыми доменами
4. **Установите `object-src 'none'`** для блокировки Flash и плагинов
5. **Используйте `report-uri`** или `report-to` для мониторинга нарушений CSP

**Пример строгой CSP для production:**

```python
CSP_DEFAULT_SRC = "'self'"
CSP_SCRIPT_SRC = "'self' https://cdn.example.com"
CSP_STYLE_SRC = "'self' https://cdn.example.com"
CSP_IMG_SRC = "'self' data: https:"
CSP_CONNECT_SRC = "'self' https://api.example.com"
CSP_FONT_SRC = "'self' https://cdn.example.com"
CSP_OBJECT_SRC = "'none'"
CSP_MEDIA_SRC = "'self'"
CSP_FRAME_SRC = "'none'"
CSP_BASE_URI = "'self'"
CSP_FORM_ACTION = "'self'"
```

### 2. HTTP Strict Transport Security (HSTS)

**Header:** `Strict-Transport-Security`

**Цель:** Защита от MITM-атак и downgrade-атак.

**Как работает:** HSTS указывает браузеру использовать только HTTPS для соединения с сайтом в течение указанного времени.

**Предотвращаемые атаки:**
- Man-in-the-Middle (MITM) атаки
- SSL stripping атаки
- Protocol downgrade атаки

**Настройки в settings.py:**

```python
# Включение/выключение HSTS
HSTS_ENABLED = True

# Максимальное время действия (в секундах)
HSTS_MAX_AGE = 31536000  # 1 год

# Включать поддомены
HSTS_INCLUDE_SUBDOMAINS = True

# Добавить в HSTS preload list
HSTS_PRELOAD = True
```

**Пример значения HSTS:**

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

**Рекомендации:**

1. **Не включайте HSTS в development** (middleware автоматически отключает в DEBUG=True)
2. **Начните с небольшого max-age** (например, 300 секунд) для тестирования
3. **Постепенно увеличивайте max-age** до 31536000 (1 год)
4. **Используйте includeSubDomains** для защиты поддоменов
5. **Добавьте сайт в HSTS preload list** после тестирования
6. **Убедитесь в наличии действительного SSL-сертификата** перед включением

**Предупреждение:** После включения HSTS с большим max-age пользователи не смогут получить доступ к сайту по HTTP даже при проблемах с SSL-сертификатом.

### 3. X-Content-Type-Options

**Header:** `X-Content-Type-Options`

**Цель:** Защита от MIME-sniffing атак.

**Как работает:** Предотвращает автоматическое определение типа содержимого браузером (MIME-sniffing).

**Предотвращаемые атаки:**
- MIME-sniffing атаки
- Загрузка вредоносных файлов как исполняемых

**Настройки в settings.py:**

```python
X_CONTENT_TYPE_OPTIONS = "nosniff"
```

**Пример значения:**

```
X-Content-Type-Options: nosniff
```

**Рекомендации:**

1. **Всегда используйте `nosniff`** - это стандарт безопасности
2. **Убедитесь в правильности Content-Type** для всех статических файлов
3. **Не изменяйте это значение** без веской причины

### 4. X-Frame-Options

**Header:** `X-Frame-Options`

**Цель:** Защита от clickjacking атак.

**Как работает:** Контролирует, может ли страница быть загружена во фрейме.

**Предотвращаемые атаки:**
- Clickjacking
- UI redress attacks

**Настройки в settings.py:**

```python
# Возможные значения:
# DENY - полная блокировка фреймов
# SAMEORIGIN - разрешены фреймы только с того же домена
# ALLOW-FROM uri - разрешены фреймы с указанного URI (устарело)
X_FRAME_OPTIONS = "DENY"
```

**Пример значения:**

```
X-Frame-Options: DENY
```

**Рекомендации:**

1. **Используйте `DENY`** для максимальной защиты
2. **Используйте `SAMEORIGIN`** если вам нужно встраивать свои страницы во фреймы
3. **Не используйте `ALLOW-FROM`** - это устаревший механизм
4. **Рассмотрите CSP frame-ancestors** как альтернативу для более гибкого контроля

**Пример с CSP frame-ancestors:**

```python
CSP_FRAME_SRC = "'none'"
# Добавить в CSP: frame-ancestors 'self' https://trusted.example.com
```

### 5. X-XSS-Protection

**Header:** `X-XSS-Protection`

**Цель:** Защита от XSS-атак в старых браузерах.

**Как работает:** Включает встроенный XSS-фильтр браузера.

**Предотвращаемые атаки:**
- Cross-Site Scripting (XSS) в старых браузерах

**Настройки в settings.py:**

```python
# Возможные значения:
# 0 - отключить фильтр
# 1 - включить фильтр
# 1; mode=block - включить фильтр и блокировать страницу при обнаружении XSS
X_XSS_PROTECTION = "1; mode=block"
```

**Пример значения:**

```
X-XSS-Protection: 1; mode=block
```

**Рекомендации:**

1. **Используйте `1; mode=block`** для максимальной защиты
2. **Не полагайтесь только на этот header** - CSP более эффективен
3. **Этот header менее важен** в современных браузерах с поддержкой CSP
4. **Рассмотрите отключение (`0`)** если используете строгую CSP

### 6. Referrer-Policy

**Header:** `Referrer-Policy`

**Цель:** Контроль информации о реферере.

**Как работает:** Определяет, какая информация о реферере отправляется при переходах.

**Предотвращаемые атаки:**
- Утечка чувствительной информации через реферер
- Отслеживание пользователей

**Настройки в settings.py:**

```python
# Возможные значения:
# no-referrer - не отправлять реферер
# no-referrer-when-downgrade - отправлять только при HTTPS->HTTPS
# origin - отправлять только origin (без path)
# origin-when-cross-origin - полный реферер для same-origin, только origin для cross-origin
# same-origin - отправлять только для same-origin
# strict-origin - отправлять только origin для HTTPS->HTTPS
# strict-origin-when-cross-origin - строгая политика для cross-origin
# unsafe-url - всегда отправлять полный реферер (не рекомендуется)
REFERRER_POLICY = "strict-origin-when-cross-origin"
```

**Пример значения:**

```
Referrer-Policy: strict-origin-when-cross-origin
```

**Рекомендации:**

1. **Используйте `strict-origin-when-cross-origin`** для баланса безопасности и функциональности
2. **Избегайте `unsafe-url`** - это может привести к утечке данных
3. **Рассмотрите `no-referrer`** для максимальной приватности
4. **Тестируйте функциональность** после изменения политики

### 7. Permissions-Policy

**Header:** `Permissions-Policy` (ранее Feature-Policy)

**Цель:** Контроль доступа к браузерным API и функциям.

**Как работает:** Ограничивает или отключает доступ к определенным браузерным API.

**Предотвращаемые атаки:**
- Несанкционированный доступ к камере, микрофону, геолокации
- Утечка информации о пользователе

**Настройки в settings.py:**

```python
# Формат: feature=() для отключения, feature=(origin) для разрешения
PERMISSIONS_POLICY = "geolocation=(), camera=(), microphone=()"
```

**Пример значения:**

```
Permissions-Policy: geolocation=(), camera=(), microphone=()
```

**Доступные функции:**

- `geolocation` - геолокация
- `camera` - камера
- `microphone` - микрофон
- `payment` - Payment Request API
- `usb` - WebUSB
- `magnetometer` - магнитометр
- `gyroscope` - гироскоп
- `accelerometer` - акселерометр
- `ambient-light-sensor` - датчик освещенности
- `autoplay` - автозапуск медиа
- `fullscreen` - полноэкранный режим
- `picture-in-picture` - картина в картинке

**Рекомендации:**

1. **Отключайте неиспользуемые функции** для повышения безопасности
2. **Разрешайте только необходимые функции** для конкретных origin
3. **Регулярно проверяйте** список разрешенных функций
4. **Тестируйте функциональность** после изменения политики

**Пример для сайта с картами:**

```python
PERMISSIONS_POLICY = "geolocation=(self), camera=(), microphone=()"
```

## Настройка

### Включение/выключение Security Headers

```python
# Включить все security headers
SECURITY_HEADERS_ENABLED = True

# Выключить все security headers (не рекомендуется в production)
SECURITY_HEADERS_ENABLED = False
```

### Настройка отдельных headers

Каждый security header может быть настроен индивидуально через соответствующую переменную в `settings.py`.

### Environment Variables

Все настройки могут быть переопределены через environment variables:

```bash
# Включить/выключить security headers
export SECURITY_HEADERS_ENABLED=True

# Настроить CSP
export CSP_ENABLED=True
export CSP_DEFAULT_SRC="'self'"
export CSP_SCRIPT_SRC="'self' 'unsafe-inline' 'unsafe-eval'"

# Настроить HSTS
export HSTS_ENABLED=True
export HSTS_MAX_AGE=31536000
export HSTS_INCLUDE_SUBDOMAINS=True
export HSTS_PRELOAD=True

# Настроить другие headers
export X_FRAME_OPTIONS=DENY
export X_CONTENT_TYPE_OPTIONS=nosniff
export X_XSS_PROTECTION="1; mode=block"
export REFERRER_POLICY=strict-origin-when-cross-origin
export PERMISSIONS_POLICY="geolocation=(), camera=(), microphone=()"
```

### Development vs Production

**Development (DEBUG=True):**
- HSTS автоматически отключен
- CSP может быть более расслабленной
- Логирование на уровне DEBUG

**Production (DEBUG=False):**
- Все security headers включены
- Строгие политики CSP
- Логирование на уровне INFO/WARNING

## Тестирование

### Запуск тестов

```bash
# Запустить все тесты security headers
pytest apps/core/tests_security_headers.py -v

# Запустить конкретный тест
pytest apps/core/tests_security_headers.py::TestSecurityHeadersMiddleware::test_middleware_adds_all_headers -v

# Запустить с покрытием
pytest apps/core/tests_security_headers.py --cov=apps.core.security_headers -v
```

### Проверка headers в браузере

1. Откройте Developer Tools (F12)
2. Перейдите на вкладку Network
3. Выполните запрос к любому endpoint
4. Проверьте Response Headers

### Проверка headers через curl

```bash
curl -I https://your-domain.com/
```

Ожидаемые headers:

```
HTTP/2 200
content-security-policy: default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; ...
strict-transport-security: max-age=31536000; includeSubDomains; preload
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin
permissions-policy: geolocation=(), camera=(), microphone=()
```

### Проверка через онлайн-инструменты

- [Security Headers](https://securityheaders.com/) - проверка security headers
- [Mozilla Observatory](https://observatory.mozilla.org/) - комплексная проверка безопасности
- [CSP Evaluator](https://csp-evaluator.withgoogle.com/) - оценка CSP

## Логирование

Security headers логируются на уровне DEBUG в файл `logs/security_headers.log`:

```python
# В config/settings.py настроен логгер
"security_headers": {
    "handlers": ["console", "security_headers_file"],
    "level": "DEBUG",
}
```

Пример лога:

```
2024-01-09 10:30:00 DEBUG security_headers Added CSP header: default-src 'self'; script-src 'self' ...
2024-01-09 10:30:00 DEBUG security_headers Added HSTS header: max-age=31536000; includeSubDomains; preload
2024-01-09 10:30:00 DEBUG security_headers Added X-Content-Type-Options header: nosniff
```

## Рекомендации по безопасности

### Минимальная конфигурация

Для базовой защиты используйте следующие настройки:

```python
SECURITY_HEADERS_ENABLED = True
CSP_ENABLED = True
CSP_DEFAULT_SRC = "'self'"
CSP_SCRIPT_SRC = "'self' 'unsafe-inline'"
CSP_STYLE_SRC = "'self' 'unsafe-inline'"
CSP_IMG_SRC = "'self' data: https:"
CSP_OBJECT_SRC = "'none'"
CSP_FRAME_SRC = "'none'"

HSTS_ENABLED = True
HSTS_MAX_AGE = 31536000
HSTS_INCLUDE_SUBDOMAINS = True
HSTS_PRELOAD = True

X_FRAME_OPTIONS = "DENY"
X_CONTENT_TYPE_OPTIONS = "nosniff"
X_XSS_PROTECTION = "1; mode=block"
REFERRER_POLICY = "strict-origin-when-cross-origin"
PERMISSIONS_POLICY = "geolocation=(), camera=(), microphone=()"
```

### Строгая конфигурация (Production)

Для максимальной безопасности в production:

```python
SECURITY_HEADERS_ENABLED = True
CSP_ENABLED = True
CSP_DEFAULT_SRC = "'self'"
CSP_SCRIPT_SRC = "'self'"
CSP_STYLE_SRC = "'self'"
CSP_IMG_SRC = "'self' data: https://cdn.example.com"
CSP_CONNECT_SRC = "'self' https://api.example.com"
CSP_FONT_SRC = "'self' https://cdn.example.com"
CSP_OBJECT_SRC = "'none'"
CSP_MEDIA_SRC = "'self'"
CSP_FRAME_SRC = "'none'"
CSP_BASE_URI = "'self'"
CSP_FORM_ACTION = "'self'"

HSTS_ENABLED = True
HSTS_MAX_AGE = 63072000  # 2 года
HSTS_INCLUDE_SUBDOMAINS = True
HSTS_PRELOAD = True

X_FRAME_OPTIONS = "DENY"
X_CONTENT_TYPE_OPTIONS = "nosniff"
X_XSS_PROTECTION = "1; mode=block"
REFERRER_POLICY = "strict-origin-when-cross-origin"
PERMISSIONS_POLICY = "geolocation=(), camera=(), microphone=(), payment=()"
```

### Отключение в Development

Для удобства разработки:

```python
# В .env для development
DEBUG=True
SECURITY_HEADERS_ENABLED=True
CSP_ENABLED=True
HSTS_ENABLED=False  # Отключить HSTS в dev
CSP_SCRIPT_SRC="'self' 'unsafe-inline' 'unsafe-eval'"
CSP_STYLE_SRC="'self' 'unsafe-inline'"
```

## Устранение неполадок

### Проблема: Сайт не работает после включения CSP

**Причина:** Слишком строгая CSP блокирует необходимые ресурсы.

**Решение:**
1. Откройте Developer Tools → Console
2. Найдите ошибки CSP
3. Добавьте необходимые источники в настройки CSP
4. Используйте CSP report-uri для мониторинга

### Проблема: Пользователи не могут получить доступ после включения HSTS

**Причина:** Проблемы с SSL-сертификатом или слишком большой max-age.

**Решение:**
1. Проверьте SSL-сертификат
2. Уменьшите HSTS_MAX_AGE
3. Очистите HSTS cache в браузере пользователей
4. Используйте HSTS preload removal service

### Проблема: Фреймы/встраивание не работают

**Причина:** X-Frame-Options или CSP блокируют фреймы.

**Решение:**
1. Измените X_FRAME_OPTIONS на SAMEORIGIN
2. Настройте CSP frame-ancestors для разрешения нужных origin
3. Рассмотрите использование CSP вместо X-Frame-Options

### Проблема: Логи не записываются

**Причина:** Проблемы с правами на запись или путями.

**Решение:**
1. Проверьте существование директории logs/
2. Проверьте права на запись
3. Проверьте конфигурацию LOGGING в settings.py

## Дополнительные ресурсы

- [MDN Web Security](https://developer.mozilla.org/en-US/docs/Web/Security)
- [OWASP Secure Headers Project](https://owasp.org/www-project-secure-headers/)
- [Content Security Policy Level 3](https://www.w3.org/TR/CSP3/)
- [HTTP Strict Transport Security (HSTS)](https://tools.ietf.org/html/rfc6797)
- [Referrer Policy](https://www.w3.org/TR/referrer-policy/)
- [Permissions Policy](https://www.w3.org/TR/permissions-policy/)

## Изменения

### Версия 1.0 (2024-01-09)

- Реализован SecurityHeadersMiddleware
- Добавлены все основные security headers
- Добавлена поддержка настройки через settings.py
- Добавлено логирование security headers
- Созданы тесты для middleware
- Создана документация
