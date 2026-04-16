from app.main import build_idempotency_key


def test_build_idempotency_key_is_deterministic() -> None:
    a = build_idempotency_key("r1", "rollback", "auth-prod")
    b = build_idempotency_key("r1", "rollback", "auth-prod")
    c = build_idempotency_key("r2", "rollback", "auth-prod")

    assert a == b
    assert a != c
