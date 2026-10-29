import unittest
from unittest.mock import patch
from nhqm_ratelimit import RateLimiter, RateLimitExceeded


class TestRateLimiter(unittest.TestCase):
    def test_basic_and_per_key(self):
        with patch("nhqm_ratelimit.core.monotonic", return_value=10):
            r = RateLimiter(2, 60)
            self.assertEqual(r.check("a").remaining, 1)
            self.assertTrue(r.check("a").allowed)
            denied = r.check("a")
            self.assertFalse(denied.allowed)
            self.assertEqual(denied.retry_after, 60)
            self.assertTrue(r.check("b").allowed)

    def test_expiry(self):
        r = RateLimiter(1, 10)
        with patch("nhqm_ratelimit.core.monotonic", return_value=0):
            self.assertTrue(r.check("a").allowed)
        with patch("nhqm_ratelimit.core.monotonic", return_value=9.5):
            self.assertFalse(r.check("a").allowed)
        with patch("nhqm_ratelimit.core.monotonic", return_value=10):
            self.assertTrue(r.check("a").allowed)

    def test_exception(self):
        r = RateLimiter(1, 10)
        with patch("nhqm_ratelimit.core.monotonic", return_value=0):
            r.require("x")
            with self.assertRaises(RateLimitExceeded):
                r.require("x")

    def test_cleanup_reset(self):
        r = RateLimiter(1, 10)
        with patch("nhqm_ratelimit.core.monotonic", return_value=0):
            r.check("x")
        with patch("nhqm_ratelimit.core.monotonic", return_value=11):
            self.assertEqual(r.cleanup(), 1)
            self.assertEqual(r.active_keys, 0)
            r.check("x")
            r.reset("x")
            self.assertEqual(r.active_keys, 0)

    def test_invalid(self):
        for limit, window in [(0, 10), (1, 0), (1, float("nan")), (True, 10)]:
            with self.assertRaises(ValueError):
                RateLimiter(limit, window)

    def test_max_keys(self):
        r = RateLimiter(1, 10, max_keys=1)
        with patch("nhqm_ratelimit.core.monotonic", return_value=0):
            r.check("a")
            with self.assertRaises(RuntimeError):
                r.check("b")
        with patch("nhqm_ratelimit.core.monotonic", return_value=11):
            self.assertTrue(r.check("b").allowed)


if __name__ == "__main__":
    unittest.main()
