from __future__ import annotations

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.db import connection
from django.utils.functional import cached_property

User = get_user_model()


class EstimatedCountPaginator(Paginator):
    """
    Paginator that uses PostgreSQL statistics for fast count() on large tables.
    """

    """
    GOAL: Return a fast (possibly approximate) object count for pagination.

    PARAMETERS:
      self: EstimatedCountPaginator - Paginator instance - Not None

    RETURNS:
      int - Total number of objects for pagination - Always >= 0

    RAISES:
      None (falls back to exact count on errors)

    GUARANTEES:
      - Uses exact count when queryset has filters (WHERE) or DB is not PostgreSQL
      - Uses pg_class.reltuples estimate for simple unfiltered querysets on PostgreSQL
      - Never raises; falls back to Django's exact count
    """
    @cached_property
    def count(self) -> int:  # type: ignore[override]
        """
        Use pg_class.reltuples for unfiltered PostgreSQL querysets; otherwise use exact count.
        """
        try:
            if connection.vendor != "postgresql":
                return int(super().count)

            qs = self.object_list
            if not hasattr(qs, "query") or qs.query.where:
                return int(super().count)

            table_name = qs.model._meta.db_table
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT reltuples::bigint FROM pg_class WHERE oid = to_regclass(%s)",
                    [table_name],
                )
                row = cursor.fetchone()

            if not row or row[0] is None:
                return int(super().count)

            estimated = max(0, int(row[0]))
            if estimated <= int(getattr(self, "per_page", 0) or 0):
                return int(super().count)

            return estimated
        except Exception:
            return int(super().count)


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    paginator = EstimatedCountPaginator
    show_full_result_count = False


@admin.register(Group)
class GroupAdmin(DjangoGroupAdmin):
    paginator = EstimatedCountPaginator
    show_full_result_count = False
