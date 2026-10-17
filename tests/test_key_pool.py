"""
evaluation/key_pool.py and the rotation logic in run_eval_ramdocs_clean.run_query.

Rotation must move on ONLY when a key's daily quota is spent or it is rejected, back off on
the same key for a per-minute throttle, never switch for an error rotation cannot fix, stop
cleanly when every key is spent, and never print a key value. Fake errors only; no network.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evaluation"))

import key_pool as kp  # noqa: E402
import run_eval_ramdocs_clean as rc  # noqa: E402

DAILY = ("Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-120b` in "
         "organization `org_x` on tokens per day (TPD): Limit 200000, Used 199990'}}")
MINUTE = ("Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-120b` on "
          "tokens per minute (TPM): Limit 8000, Used 7900'}}")
INVALID = "Error code: 401 - {'error': {'message': 'Invalid API Key', 'code': 'invalid_api_key'}}"
TOO_BIG = "Error code: 413 - {'error': {'message': 'Request too large for model on tokens per minute'}}"


def env(*pairs):
    return {n: v for n, v in pairs}


@pytest.mark.parametrize("msg,kind", [(DAILY, "daily_cap"), (MINUTE, "rate_minute"), (INVALID, "invalid"),
                                       (TOO_BIG, "too_large"), ("connection reset", "other"), ("", "other")])
def test_error_classification(msg, kind):
    assert kp.classify_error(msg) == kind


def test_pool_uses_keys_in_order_skips_blanks_and_ignores_gaps():
    pool = kp.KeyPool(env(("GROQ_API_KEY", "k1"), ("GROQ_API_KEY_2", ""), ("GROQ_API_KEY_3", "k3"),
                          ("GROQ_API_KEY_7", "k7"), ("OTHER", "x")))
    assert pool.names == ["GROQ_API_KEY", "GROQ_API_KEY_3", "GROQ_API_KEY_7"]
    assert pool.current() == ("GROQ_API_KEY", "k1")


def test_retire_advances_and_reports_exhaustion():
    pool = kp.KeyPool(env(("GROQ_API_KEY", "a"), ("GROQ_API_KEY_2", "b")))
    assert pool.retire("daily_cap") == "GROQ_API_KEY_2"
    assert pool.current() == ("GROQ_API_KEY_2", "b") and not pool.exhausted
    assert pool.retire("invalid") is None
    assert pool.exhausted
    with pytest.raises(RuntimeError):
        pool.current()


def test_status_and_repr_never_contain_key_values():
    pool = kp.KeyPool(env(("GROQ_API_KEY", "SECRET-ONE"), ("GROQ_API_KEY_2", "SECRET-TWO")))
    pool.retire("daily_cap")
    assert "SECRET" not in pool.status() and "SECRET" not in str(pool.names)


def run(monkeypatch, pool, script):
    """Run run_query with a runner that raises/returns per `script`; return (result, key names applied)."""
    applied = []
    monkeypatch.setattr(rc, "apply_key", lambda pair: applied.append(pair[0]) or pair[0])
    monkeypatch.setattr(rc.time, "sleep", lambda s: applied.append(f"sleep{s}"))
    steps = iter(script)

    def runner(rec, order):
        s = next(steps)
        if isinstance(s, Exception):
            raise s
        return s

    return rc.run_query(runner, {"_qid": "rd0000"}, "original", pool), applied


def test_daily_cap_switches_key_and_retries_the_same_query(monkeypatch):
    pool = kp.KeyPool(env(("GROQ_API_KEY", "a"), ("GROQ_API_KEY_2", "b")))
    res, applied = run(monkeypatch, pool, [RuntimeError(DAILY), {"ok": 1}])
    assert res == {"ok": 1} and applied == ["GROQ_API_KEY_2"]


def test_invalid_key_is_skipped(monkeypatch):
    pool = kp.KeyPool(env(("GROQ_API_KEY", "a"), ("GROQ_API_KEY_2", "b")))
    res, applied = run(monkeypatch, pool, [RuntimeError(INVALID), {"ok": 1}])
    assert res == {"ok": 1} and applied == ["GROQ_API_KEY_2"]


def test_minute_throttle_waits_on_the_same_key_and_never_switches(monkeypatch):
    pool = kp.KeyPool(env(("GROQ_API_KEY", "a"), ("GROQ_API_KEY_2", "b")))
    res, applied = run(monkeypatch, pool, [RuntimeError(MINUTE), RuntimeError(MINUTE), {"ok": 1}])
    assert res == {"ok": 1} and applied == ["sleep30", "sleep60"]
    assert pool.current()[0] == "GROQ_API_KEY"


def test_too_large_and_other_errors_are_raised_not_rotated(monkeypatch):
    for msg in (TOO_BIG, "something else"):
        pool = kp.KeyPool(env(("GROQ_API_KEY", "a"), ("GROQ_API_KEY_2", "b")))
        with pytest.raises(RuntimeError):
            run(monkeypatch, pool, [RuntimeError(msg)])
        assert pool.current()[0] == "GROQ_API_KEY"


def test_all_keys_spent_stops_with_poolexhausted(monkeypatch):
    pool = kp.KeyPool(env(("GROQ_API_KEY", "a"), ("GROQ_API_KEY_2", "b")))
    with pytest.raises(rc.PoolExhausted):
        run(monkeypatch, pool, [RuntimeError(DAILY), RuntimeError(DAILY)])


def test_without_a_pool_errors_propagate(monkeypatch):
    with pytest.raises(RuntimeError):
        run(monkeypatch, None, [RuntimeError(DAILY)])


def test_persistent_minute_throttle_eventually_gives_up(monkeypatch):
    pool = kp.KeyPool(env(("GROQ_API_KEY", "a")))
    with pytest.raises(RuntimeError):
        run(monkeypatch, pool, [RuntimeError(MINUTE)] * 6)


def test_rotate_and_key_env_are_mutually_exclusive(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["x", "--tag", "t", "--rotate-keys", "--key-env", "GROQ_API_KEY_2"])
    with pytest.raises(SystemExit):
        rc.main()
