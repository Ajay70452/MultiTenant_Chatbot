import time
import sys
import os

# Ensure project root is on sys.path so `src` package can be imported when running tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.db import wait_for_db


def test_wait_for_db_succeeds_after_retries():
    class FakeEngine:
        def __init__(self, fail_times=2):
            self.attempt = 0
            self.fail_times = fail_times

        def connect(self):
            if self.attempt < self.fail_times:
                self.attempt += 1
                raise Exception("db not ready")
            class Conn:
                def close(self):
                    pass
            return Conn()

    fe = FakeEngine(fail_times=2)
    # use small delay so tests run fast
    result = wait_for_db(retries=5, delay=0.01, engine_obj=fe)
    assert result is True
    assert fe.attempt == 2


def test_wait_for_db_fails_when_exceeding_retries():
    class FakeEngine:
        def __init__(self):
            self.attempt = 0

        def connect(self):
            self.attempt += 1
            raise Exception("still down")

    fe = FakeEngine()
    result = wait_for_db(retries=3, delay=0.01, engine_obj=fe)
    assert result is False
    assert fe.attempt == 4  # initial attempt + 3 retries
