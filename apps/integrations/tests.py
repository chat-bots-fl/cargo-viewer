from __future__ import annotations

from django.test import TestCase

from apps.integrations.rate_limiter import RateLimiter


class RateLimiterTests(TestCase):
    def test_can_request_depletes_tokens(self):
        limiter = RateLimiter(requests_per_minute=1)
        self.assertTrue(limiter.can_request())
        self.assertFalse(limiter.can_request())

