# 📑 API CONTRACTS v3.2 (Contracts 1.1–5.4)

**Дата:** 7 января 2026  
**Версия:** 3.2 (v3.1 + HAR Validation Updates)

---

## 🧾 Единая таблица контрактов (16)

| Contract | Модуль | Метод/сервис | Назначение | Где описано |
|---|---|---|---|---|
| 1.1 | M1 | `TelegramAuthService.validate_init_data()` | Валидация `initData` Telegram WebApp (HMAC + max_age) | `FINAL_PROJECT_DOCUMENTATION_v3.2.md` |
| 1.2 | M1 | `SessionService.create_session()` | Создание сессии водителя (Redis) | `FINAL_PROJECT_DOCUMENTATION_v3.2.md` |
| 1.3 | M1 | `TokenService.validate_session()` | Проверка session token | `FINAL_PROJECT_DOCUMENTATION_v3.2.md` |
| 1.4 | M1 | `CargoTechAuthService.login()` | Логин в CargoTech API + получение Bearer token | `FINAL_PROJECT_DOCUMENTATION_v3.2.md` |
| 2.1 | M2 | `CargoAPIClient.fetch_cargos()` | Запрос списка/деталей грузов в CargoTech API | `FINAL_PROJECT_DOCUMENTATION_v3.2.md` |
| 2.2 | M2 | `CargoService.format_cargo_card()` | Форматирование ответа API в UI‑карточки | `FINAL_PROJECT_DOCUMENTATION_v3.2.md` |
| 2.3 | M2 | `CargoService.get_cargos()` | Агрегация + кэширование (per‑user) | `FINAL_PROJECT_DOCUMENTATION_v3.2.md` |
| 2.4 | M2 | `DictionaryService.search_cities()` | Поиск городов (автокомплит) | `API_CONTRACTS_v3.2.md` |
| 3.1 | M3 | `FilterService.validate_filters()` | Валидация фильтров (в т.ч. `filter[wv]`) | `FINAL_PROJECT_DOCUMENTATION_v3.2.md` |
| 3.2 | M3 | `FilterService.build_query()` | Построение query для CargoTech API | `FINAL_PROJECT_DOCUMENTATION_v3.2.md` |
| 4.1 | M4 | `TelegramBotService.handle_response()` | Обработка отклика водителя | `FINAL_PROJECT_DOCUMENTATION_v3.2.md` |
| 4.2 | M4 | `TelegramBotService.send_status()` | Отправка статусов/обновлений в Telegram | `FINAL_PROJECT_DOCUMENTATION_v3.2.md` |
| 5.1 | M5 | `PaymentService.create_payment()` | Создание платежа в ЮKassa (возврат `confirmation_url`) | `M5_SUBSCRIPTION_PAYMENT_FULL.md` |
| 5.2 | M5 | `PaymentService.process_webhook()` | Обработка webhook ЮKassa (signature + idempotency) | `M5_SUBSCRIPTION_PAYMENT_FULL.md` |
| 5.3 | M5 | `SubscriptionService.activate_from_payment()` | Активация/продление подписки после оплаты | `M5_SUBSCRIPTION_PAYMENT_FULL.md` |
| 5.4 | M5 | `PromoCodeService.create_promo_code()` | Создание промокодов (админ) | `M5_SUBSCRIPTION_PAYMENT_FULL.md` |

---

## 🧭 Навигация по деталям

- Contracts `1.1–4.2`: `FINAL_PROJECT_DOCUMENTATION_v3.2.md` (разделы `Contract 1.1` … `Contract 4.2`)
- Contracts `5.1–5.4`: `M5_SUBSCRIPTION_PAYMENT_FULL.md` (разделы `Contract 5.1` … `Contract 5.4`)

---

### Contract 1.4: Авторизация CargoTech API (Bearer Token)

CargoTech API использует **Bearer Token** (Laravel Sanctum). Токен получается через `/v1/auth/login` и
передаётся во всех последующих запросах через заголовок `Authorization`.

**Login**

- Endpoint: `POST https://api.cargotech.pro/v1/auth/login`
- Request JSON: `{"phone":"+7 ...","password":"***","remember":true}`
- Response `200`:

```json
{"data":{"token":"12345|<opaque_token>"}}
```

**Use token**

- Header: `Authorization: Bearer <token>`
- Проверка: `GET https://api.cargotech.pro/v1/me`
- Cargo list: `GET https://api.cargotech.pro/v2/cargos/views?...`

Примечание: в реальном CargoTech WebApp токен хранится в `localStorage`. В server‑side интеграции
токен можно хранить в кэше (Redis) и получать заново при `401`.

### Использование токена (подтверждено HAR анализом)

Токен передается в каждом запросе через заголовок Authorization:

```
Authorization: Bearer {token}
```

Пример:
```
Authorization: Bearer 12345|AbCdEf...
```

**ВАЖНО:** При захвате HAR через некоторые инструменты заголовок
Authorization может не отображаться из соображений безопасности.
Для проверки используйте Chrome DevTools → Network → Headers.

### Механизм авторизации (VERIFIED 2026-01-08)

API использует Bearer Token авторизацию через заголовок Authorization.

**Token Storage:**
- Frontend: `localStorage.accessToken`
- Backend: Redis cache (`cargotech:api:token`, TTL 24h)

**Token Format:**
`{id}|{hash}`  
Пример: `12345|AbCdEf...`  
Длина: 54 символа

**Request Example:**

```
GET /v2/cargos/views
Authorization: Bearer 12345|AbCdEf...
Accept: application/json
```

**ВАЖНО:**
- ✅ Bearer Token РАБОТАЕТ (HTTP 200)
- ❌ Cookie-based auth НЕ поддерживается (CORS blocked)

### Contract 2.1: Фактические параметры запроса

| Параметр | Тип | Обязательный | Описание | Пример |
|---|---|---|---|---|
| `filter[start_point_id]` | int | нет | ID города загрузки | 62 |
| `filter[finish_point_id]` | int | нет | ID города выгрузки | 39 |
| `filter[start_point_type]` | int | **да*** | Тип точки отправления (1=город) | 1 |
| `filter[finish_point_type]` | int | **да*** | Тип точки назначения (1=город) | 1 |
| `filter[start_point_radius]` | int | нет | Радиус от точки загрузки (км) | 50 |
| `filter[finish_point_radius]` | int | нет | Радиус от точки выгрузки (км) | 50 |
| `filter[start_date]` | date | нет | Дата загрузки (YYYY-MM-DD) | 2026-01-01 |
| `filter[mode]` | string | **да** | Режим отображения | my |
| `filter[user_id]` | int | **да** | ID пользователя (0=текущий) | 0 |
| `filter[wv]` | string | нет | Вес-объем (формат: "{вес}-{объем}") | 15-65 |
| `filter[load_types]` | string | нет | ID типов загрузки (CSV) | 1,2,3 |
| `filter[truck_types]` | string | нет | ID типов транспорта (CSV) | 1,2,4 |
| `filter[distance]` | string | нет | Диапазон расстояния в км ("min,max") | 0,9999 |
| `filter[price]` | string | нет | Диапазон цены в копейках ("min,max") | 0,99999900 |
| `filter[price_per_km]` | string | нет | Диапазон цены за км в копейках ("min,max") | 0,99900 |
| `filter[owner_company]` | string | нет | ИНН компании-владельца | 7700000000 |
| `include` | string | **да** | Включить связанные данные | contacts |
| `limit` | int | **да** | Количество записей на страницу | 20 |
| `offset` | int | **да** | Смещение для пагинации | 0 |

**Примечание:**
- `filter[mode]` = "my" - только мои грузы, "all" - все доступные
- `filter[user_id]` обычно `0` (текущий), но может быть и явным ID пользователя
- `filter[start_point_type]` обязателен при использовании `filter[start_point_id]` (аналогично: `filter[finish_point_type]` при `filter[finish_point_id]`)
- `filter[load_types]`, `filter[truck_types]` в HAR передаются как CSV список ID (например: `"1,2,3"`)
- `filter[distance]`, `filter[price]`, `filter[price_per_km]` в HAR передаются как диапазоны `"min,max"` (строки)

### Обязательные параметры (на основе анализа production API)

Следующие параметры используются в **100% запросов** и должны присутствовать:

```python
# apps/integrations/cargotech_client.py

DEFAULT_CARGO_LIST_PARAMS = {
    "filter[mode]": "my",           # режим отображения
    "filter[user_id]": 0,           # текущий пользователь
    "include": "contacts",          # включить контакты
    "limit": 20,                    # записей на страницу
    "offset": 0,                    # начальное смещение
}

def build_cargo_list_params(filters: dict) -> dict:
    """
    Построение параметров запроса списка грузов.

    Args:
        filters: пользовательские фильтры

    Returns:
        Полный набор параметров для API
    """
    params = DEFAULT_CARGO_LIST_PARAMS.copy()

    # Добавляем пользовательские фильтры
    if filters.get("start_point_id"):
        params["filter[start_point_id]"] = filters["start_point_id"]
        params["filter[start_point_type]"] = 1  # обязательно при start_point_id
        params["filter[start_point_radius]"] = filters.get("start_point_radius", 50)

    if filters.get("finish_point_id"):
        params["filter[finish_point_id]"] = filters["finish_point_id"]
        params["filter[finish_point_type]"] = 1
        params["filter[finish_point_radius]"] = filters.get("finish_point_radius", 50)

    if filters.get("start_date"):
        params["filter[start_date]"] = filters["start_date"]

    if filters.get("weight_volume"):
        wv_filter = FilterService.validate_weight_volume(filters["weight_volume"])
        params.update(wv_filter)

    if filters.get("load_types"):
        params["filter[load_types]"] = filters["load_types"]  # CSV: "1,2,3"

    if filters.get("truck_types"):
        params["filter[truck_types]"] = filters["truck_types"]  # CSV: "1,2,4"

    # НОВЫЕ ПАРАМЕТРЫ (v3.2) — формат range "min,max"
    if filters.get("distance_range"):
        params["filter[distance]"] = filters["distance_range"]  # км, например: "0,9999"

    if filters.get("price_range"):
        params["filter[price]"] = filters["price_range"]  # коп, например: "0,99999900"

    if filters.get("price_per_km_range"):
        params["filter[price_per_km]"] = filters["price_per_km_range"]  # коп, например: "0,99900"

    if filters.get("owner_company"):
        params["filter[owner_company]"] = filters["owner_company"]  # ИНН

    # Пагинация
    if "offset" in filters:
        params["offset"] = filters["offset"]

    return params
```

### Contract 2.1: Комментарий к грузу (`data.extra.note`) (detail)

Cargo list endpoint `GET /v2/cargos/views` возвращает карточки грузов и **не содержит** комментарий.
Комментарий доступен только в detail view:

- Endpoint: `GET https://api.cargotech.pro/v1/carrier/cargos/{cargo_id}?source=1&include=contacts`
- Поле комментария: `data.extra.note`

Структура `extra` (10 полей):

```json
{
  "note": "По ставке без НДС возможна заправка...",
  "external_inn": null,
  "custom_cargo_type": null,
  "integrate": null,
  "is_delete_from_archive": false,
  "krugoreis": false,
  "partial_load": false,
  "note_valid": true,
  "integrate_contacts": null,
  "url": "https://cargomart.ru/orders/active?modal=..."
}
```

Полезные поля:
- `note_valid` — валидность комментария
- `url` — ссылка на источник (CargoMart)
- `krugoreis`, `partial_load` — признаки рейса/частичной загрузки
- `integrate_contacts` — интеграция контактов (если есть)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### Contract 3.1: Формат weight/volume (`filter[wv]`) [ОБНОВЛЕНО v3.2]

**ВАЖНО:** На основе анализа HAR файлов установлено, что CargoTech API
принимает **произвольные** значения фильтра вес/объем, а не фиксированные
категории.

#### Формат параметра

```
filter[wv] = "{weight}-{volume}"

где:
  weight  - вес в тоннах (поддерживает десятичные: 1, 1.5, 20)
  volume  - объем в м³ (поддерживает десятичные: 9, 15.5, 65)
```

#### Реальные примеры из production API

```
filter[wv]=1.5-9       # 1.5 тонн, 9 м³
filter[wv]=3-16        # 3 тонны, 16 м³
filter[wv]=5-36        # 5 тонн, 36 м³
filter[wv]=7.5-45      # 7.5 тонн, 45 м³
filter[wv]=10-54       # 10 тонн, 54 м³
filter[wv]=15-65       # 15 тонн, 65 м³
filter[wv]=20-83       # 20 тонн, 83 м³
```

#### Рекомендуемые frontend категории (опционально)

Для упрощения UX можно предложить пользователю стандартные категории,
но при этом разрешить кастомный ввод:

| UI Категория | API значение | Описание |
|---|---|---|
| Легкий | `1-15` | До 1 тонны, до 15 м³ |
| Малотоннажный | `3-25` | 3-5 тонн, 15-25 м³ |
| Среднетоннажный | `5-40` | 5-10 тонн, 25-40 м³ |
| Крупнотоннажный | `10-60` | 10-15 тонн, 40-60 м³ |
| Фура 20т | `15-65` | 15-20 тонн, 60-65 м³ |
| Тяжеловес | `20-120` | 20+ тонн, 82+ м³ |
| **Кастомный** | `{вес}-{объем}` | Ввод вручную |

#### Валидация на backend

```python
import re

def validate_weight_volume(value: str) -> bool:
    """
    Валидация filter[wv] параметра.

    Формат: {weight}-{volume}
    Примеры: "1-15", "1.5-9", "20-83"
    """
    if not value:
        return True  # пустое значение = без фильтра

    # Регулярное выражение: число или десятичное, дефис, число или десятичное
    pattern = r'^\d+(\.\d+)?-\d+(\.\d+)?$'

    if not re.match(pattern, value):
        return False

    # Дополнительная проверка диапазонов
    try:
        weight, volume = value.split('-')
        weight_val = float(weight)
        volume_val = float(volume)

        # Разумные пределы (можно настроить)
        if not (0.1 <= weight_val <= 1000):  # вес: 0.1т - 1000т
            return False
        if not (0.1 <= volume_val <= 200):   # объем: 0.1м³ - 200м³
            return False

        return True
    except (ValueError, AttributeError):
        return False
```

#### Обновленный Contract 3.1

```python
# apps/filtering/services.py

from django.core.exceptions import ValidationError
import re

class FilterService:

    @staticmethod
    def validate_weight_volume(value: str) -> dict:
        """
        Валидация и нормализация фильтра вес/объем.

        Args:
            value: строка формата "{weight}-{volume}"
                   или пустая строка для отключения фильтра

        Returns:
            {"filter[wv]": value} или {} если пусто

        Raises:
            ValidationError: если формат некорректен
        """
        if not value or value == "any":
            return {}

        # Валидация формата
        pattern = r'^\d+(\.\d+)?-\d+(\.\d+)?$'
        if not re.match(pattern, value):
            raise ValidationError(
                f"Invalid weight_volume format: '{value}'. "
                f"Expected format: '{{weight}}-{{volume}}', "
                f"example: '15-65' or '1.5-9'"
            )

        # Проверка диапазонов
        weight, volume = value.split('-')
        weight_val = float(weight)
        volume_val = float(volume)

        if not (0.1 <= weight_val <= 1000):
            raise ValidationError(
                f"Weight {weight_val}t out of range (0.1-1000)"
            )

        if not (0.1 <= volume_val <= 200):
            raise ValidationError(
                f"Volume {volume_val}m³ out of range (0.1-200)"
            )

        return {"filter[wv]": value}
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Contract 2.4: Справочник городов (NEW v3.2)

### Endpoint: GET /v1/dictionaries/points

Получение списка городов/населенных пунктов для автокомплита.

#### Параметры запроса

| Параметр | Тип | Обязательный | Описание |
|---|---|---|---|
| `filter[name]` | string | да | Поисковый запрос (API принимает и короткие/пустые значения; рекомендуется debounce + min length в UI) |

#### Пример запроса

```http
GET /v1/dictionaries/points?filter[name]=Моск
Authorization: Bearer {token}
```

#### Пример ответа

```json
{
  "data": [
    { "id": 1, "name": "Москва", "type": 1 },
    { "id": 62, "name": "Московский", "type": 1 }
  ],
  "meta": { "limit": 10, "offset": 0, "size": 2 }
}
```

#### Реализация автокомплита (Frontend)

```javascript
// components/CityAutocomplete.vue

<template>
  <div class="autocomplete">
    <input
      v-model="query"
      @input="handleInput"
      placeholder="Введите город..."
    />
    <ul v-if="suggestions.length">
      <li
        v-for="city in suggestions"
        :key="city.id"
        @click="selectCity(city)"
      >
        {{ city.name }}
      </li>
    </ul>
  </div>
</template>

<script>
import { ref } from 'vue';
import { debounce } from 'lodash';

export default {
  setup(props, { emit }) {
    const query = ref('');
    const suggestions = ref([]);

    const searchCities = async (searchQuery) => {
      if (searchQuery.length < 2) {
        suggestions.value = [];
        return;
      }

      try {
         const response = await fetch(
          `/api/dictionaries/points?filter[name]=${encodeURIComponent(searchQuery)}`
        );
        const data = await response.json();
        suggestions.value = data.data;
      } catch (error) {
        console.error('City search error:', error);
      }
    };

    const handleInput = debounce(() => {
      searchCities(query.value);
    }, 300);

    const selectCity = (city) => {
      emit('select', city);
      query.value = city.name;
      suggestions.value = [];
    };

    return {
      query,
      suggestions,
      handleInput,
      selectCity
    };
  }
};
</script>
```

#### Backend прокси (Django)

```python
# apps/integrations/views.py

from django.http import JsonResponse
from django.views import View
from .cargotech_client import CargoAPIClient

class CityAutocompleteView(View):
    \"\"\"Прокси для автокомплита городов\"\"\"

    def get(self, request):
        query = (request.GET.get('filter[name]') or request.GET.get('q') or '').strip()

        if len(query) < 2:
            return JsonResponse({
                'data': [],
                'error': 'Query must be at least 2 characters'
            }, status=400)

        try:
            result = CargoAPIClient.request(
                'GET',
                '/v1/dictionaries/points',
                params={'filter[name]': query}
            )
            return JsonResponse(result)

        except Exception as e:
            return JsonResponse({
                'data': [],
                'error': str(e)
            }, status=500)
```

#### Кэширование

Рекомендуется кэшировать результаты поиска на 24 часа:

```python
from django.core.cache import cache
import hashlib

def search_cities(query: str) -> list:
    # Генерируем ключ кэша
    cache_key = f\"city_search:{hashlib.md5(query.encode()).hexdigest()}\"

    # Проверяем кэш
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Запрашиваем API
    result = CargoAPIClient.request(
        'GET',
        '/v1/dictionaries/points',
        params={'filter[name]': query}
    )

    # Кэшируем на 24 часа
    cache.set(cache_key, result['data'], timeout=86400)

    return result['data']
```
