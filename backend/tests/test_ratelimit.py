from app.services.ratelimit import SlidingWindowRateLimiter


def test_allows_up_to_the_limit():
    limiter = SlidingWindowRateLimiter(max_requests=3, window_s=60)

    assert [limiter.allow("a", now=t) for t in (0, 1, 2, 3)] == [True, True, True, False]


def test_requests_expire_after_the_window():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_s=60)
    limiter.allow("a", now=0)
    limiter.allow("a", now=10)

    assert limiter.allow("a", now=59) is False
    assert limiter.allow("a", now=60) is True  # the request at t=0 has expired


def test_rejected_requests_do_not_extend_the_block():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_s=60)
    limiter.allow("a", now=0)
    for t in range(1, 60):
        limiter.allow("a", now=t)

    assert limiter.allow("a", now=60) is True


def test_keys_are_independent():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_s=60)

    assert limiter.allow("a", now=0) is True
    assert limiter.allow("b", now=0) is True
    assert limiter.allow("a", now=1) is False


def test_quiet_keys_are_forgotten():
    limiter = SlidingWindowRateLimiter(max_requests=5, window_s=60)
    for i in range(100):
        limiter.allow(f"visitor-{i}", now=0)

    limiter.allow("someone", now=120)

    assert list(limiter._hits) == ["someone"]
