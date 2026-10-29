from nhqm_ratelimit import RateLimiter

limiter = RateLimiter(limit=5, window=60)
user_id = "user-123"

result = limiter.check(user_id)
if result.allowed:
    print("Request accepted; remaining:", result.remaining)
else:
    print(f"Too many requests; retry in {result.retry_after:.1f}s")
