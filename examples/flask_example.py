"""Optional Flask example: pip install flask"""
from flask import Flask, jsonify, request
from nhqm_ratelimit import RateLimiter

app = Flask(__name__)
limiter = RateLimiter(limit=10, window=60)

@app.get("/api/status")
def status():
    # Use authenticated account IDs in production; request.remote_addr is proxy-dependent.
    key = request.remote_addr or "unknown"
    result = limiter.check(key)
    if not result.allowed:
        response = jsonify(error="Too many requests")
        response.status_code = 429
        response.headers["Retry-After"] = str(max(1, __import__("math").ceil(result.retry_after)))
        return response
    return jsonify(status="ok", remaining=result.remaining)

if __name__ == "__main__":
    app.run(debug=True)
