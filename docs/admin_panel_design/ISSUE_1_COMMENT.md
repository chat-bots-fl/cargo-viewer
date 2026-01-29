## Admin UI: единая точка входа

Сделано:
- `/admin/` стал единой точкой входа в администрирование.
- Левое меню сделано двухуровневым: **Cargo Viewer** и **Администрирование**.
- В **Cargo Viewer** выведены функции бывшего `admin-panel`: Payments, Subscriptions, Promo codes, Settings, Audit log, Cache diagnostics.
- В **Администрирование** выведены все функции Django admin (полный список приложений/моделей).
- `/admin-panel/*` убрано из UI: все legacy URL теперь редиректят на соответствующие страницы внутри `/admin/`.

Файлы:
- `config/urls.py`
- `templates/admin/nav_sidebar.html`
- `templates/admin/index.html`
- `templates/admin/cargo_viewer/payments.html`
- `templates/admin/cargo_viewer/subscriptions.html`
- `templates/admin/cargo_viewer/promocodes.html`
- `templates/admin/cargo_viewer/settings.html`
- `templates/admin/cargo_viewer/audit_log.html`
- `apps/admin_panel/views.py`
- `static/css/admin_panel.css`
- `apps/core/rate_limit_middleware.py`

Как проверить:
- открыть `/admin/` и убедиться, что видны все функции (Cargo Viewer + Администрирование)
- открыть `/admin-panel/` и убедиться, что происходит редирект на `/admin/`

