from __future__ import annotations

from django.urls import path

from apps.admin_panel import views

urlpatterns = [
    path("admin-panel/", views.dashboard, name="admin_panel_dashboard"),
    path("admin-panel/payments/", views.payment_list_view, name="admin_panel_payments"),
    path("admin-panel/subscriptions/", views.subscription_list_view, name="admin_panel_subscriptions"),
    path("admin-panel/promocodes/", views.promocode_list_view, name="admin_panel_promocodes"),
    path("admin-panel/settings/", views.settings_view, name="admin_panel_settings"),
    path("admin-panel/audit-log/", views.audit_log_view, name="admin_panel_audit_log"),
]

