import pytest

from thermovisi.retry import is_retryable_connection_error, retry_read


def test_winerror_10054_is_retryable():
    assert is_retryable_connection_error(
        OSError("[WinError 10054] An existing connection was forcibly closed by the remote host")
    )


def test_httpx_read_timeout_is_retryable():
    class ReadTimeout(Exception):
        pass

    assert is_retryable_connection_error(ReadTimeout("The read operation timed out"))


def test_retry_read_retries_connection_error_once():
    attempts = []

    def action():
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("[WinError 10054] connection reset")
        return "ok"

    result = retry_read(action, attempts=2, sleep=lambda _: None)
    assert result == "ok"
    assert len(attempts) == 2


def test_retry_read_does_not_retry_permission_error():
    attempts = []

    def action():
        attempts.append(1)
        raise RuntimeError("permission denied")

    with pytest.raises(RuntimeError, match="permission denied"):
        retry_read(action, attempts=2, sleep=lambda _: None)
    assert len(attempts) == 1
