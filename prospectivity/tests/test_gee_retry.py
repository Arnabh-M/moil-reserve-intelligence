"""Tests for prospectivity.gee_features.with_gee_retry.

The retry wrapper distinguishes transient GEE failures (quota/429/5xx/timeout),
which are worth backing off on, from deterministic code or data errors, which
are not. Both the behaviour and the message it raises are asserted here: the
message used to print the CONFIGURED attempt ceiling regardless of how many
attempts were actually spent, so a single non-retried failure read as though a
full exponential backoff had been exhausted against a flaky network. That
misreporting sent a real investigation down the wrong path.
"""

from __future__ import annotations

import pytest

from prospectivity.gee_features import GEELayerError, with_gee_retry


def test_success_returns_immediately():
    calls = []

    def fn():
        calls.append(1)
        return "value"

    assert with_gee_retry(fn, what="ok", attempts=4, base_delay=0.01) == "value"
    assert len(calls) == 1


def test_non_transient_error_is_not_retried():
    """A missing dictionary key is a code/data bug — retrying cannot help."""
    calls = []

    def fn():
        calls.append(1)
        raise RuntimeError("Dictionary.get: Dictionary does not contain key: 'ndvi'")

    with pytest.raises(GEELayerError) as exc_info:
        with_gee_retry(fn, what="code-bug", attempts=5, base_delay=0.01)

    assert len(calls) == 1, "a non-transient error must not be retried"
    message = str(exc_info.value)
    assert "after 1 attempt(s)" in message, (
        f"message must report the attempts actually spent, got: {message}"
    )
    assert "not retried" in message
    assert "after 5 attempt(s)" not in message


def test_transient_error_is_retried_until_the_ceiling():
    calls = []

    def fn():
        calls.append(1)
        raise RuntimeError("Too many concurrent aggregations")

    with pytest.raises(GEELayerError) as exc_info:
        with_gee_retry(fn, what="quota", attempts=3, base_delay=0.01)

    assert len(calls) == 3, "a transient error should use every configured attempt"
    message = str(exc_info.value)
    assert "after 3 attempt(s)" in message
    assert "retries exhausted" in message


def test_transient_error_that_recovers_reports_no_failure():
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("429 rate limit")
        return "recovered"

    assert with_gee_retry(fn, what="flaky", attempts=5, base_delay=0.01) == "recovered"
    assert len(calls) == 3


@pytest.mark.parametrize(
    "marker",
    ["quota", "rate limit", "too many", "429", "503", "500", "timed out", "deadline"],
)
def test_transient_markers_are_recognised(marker):
    calls = []

    def fn():
        calls.append(1)
        raise RuntimeError(f"GEE said: {marker}")

    with pytest.raises(GEELayerError):
        with_gee_retry(fn, what=marker, attempts=2, base_delay=0.01)

    assert len(calls) == 2, f"{marker!r} should have been treated as transient"


# ---------------------------------------------------------------------------
# Transport-level failures must be retried too.
#
# The Earth Engine client carries its own retry layer. When THAT layer gives
# up, the underlying transport error propagates here — and the original marker
# list only covered GEE-level errors (quota/429/5xx), so a DNS outage was
# classified "not transient" and the call was abandoned after one attempt.
# Observed live on 2026-09-23: a ~16 minute local resolver outage cost
# nagpur's 2025-04-01..2025-04-10 NDVI composite, which the next window then
# proved was still perfectly fetchable.
# ---------------------------------------------------------------------------

REAL_DNS_FAILURE = (
    "HTTPSConnectionPool(host='earthengine.googleapis.com', port=443): "
    "Max retries exceeded with url: /v1/projects/manganex-509408/value:compute "
    "(Caused by NameResolutionError(\"HTTPSConnection(host='earthengine.googleapis.com', "
    "port=443): Failed to resolve 'earthengine.googleapis.com' "
    "([Errno 11001] getaddrinfo failed)\"))"
)


def test_the_real_dns_failure_is_treated_as_transient():
    """Verbatim message from the 2026-09-23 outage."""
    calls = []

    def fn():
        calls.append(1)
        raise RuntimeError(REAL_DNS_FAILURE)

    with pytest.raises(GEELayerError) as exc_info:
        with_gee_retry(fn, what="dns-outage", attempts=4, base_delay=0.01)

    assert len(calls) == 4, (
        "a DNS/transport failure must use the full retry budget, not be "
        "abandoned as a permanent code error"
    )
    assert "retries exhausted" in str(exc_info.value)


def test_dns_failure_that_recovers_is_not_lost():
    """The outage recovered within a window's retry budget — the composite
    should come back rather than being dropped."""
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError(REAL_DNS_FAILURE)
        return {"ndvi_mean": 0.42}

    assert with_gee_retry(fn, what="dns-recovers", attempts=5, base_delay=0.01) == {
        "ndvi_mean": 0.42
    }
    assert len(calls) == 3


@pytest.mark.parametrize(
    "marker",
    [
        "NameResolutionError", "getaddrinfo failed", "Failed to resolve",
        "Max retries exceeded", "Connection reset by peer", "Connection aborted",
        "Connection refused", "Broken pipe", "SSL: WRONG_VERSION_NUMBER",
        "EOF occurred in violation of protocol", "Temporarily unavailable",
        "Network is unreachable",
    ],
)
def test_transport_markers_are_recognised(marker):
    calls = []

    def fn():
        calls.append(1)
        raise RuntimeError(f"HTTPSConnectionPool: {marker}")

    with pytest.raises(GEELayerError):
        with_gee_retry(fn, what=marker, attempts=2, base_delay=0.01)

    assert len(calls) == 2, f"{marker!r} should have been treated as transient"


def test_a_genuine_code_error_is_still_not_retried():
    """The widened marker list must not swallow deterministic bugs."""
    calls = []

    def fn():
        calls.append(1)
        raise RuntimeError("Dictionary.get: Dictionary does not contain key: 'ndvi'")

    with pytest.raises(GEELayerError) as exc_info:
        with_gee_retry(fn, what="code-bug", attempts=5, base_delay=0.01)

    assert len(calls) == 1
    assert "not retried" in str(exc_info.value)
