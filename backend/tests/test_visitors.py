from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.config import Settings
from app.main import create_app
from app.models import Visitor
from app.visitors import COOKIE_MAX_AGE_S, VISITOR_COOKIE, CurrentVisitor, parse_visitor_id


def make_client(settings: Settings) -> TestClient:
    app = create_app(settings)

    @app.get("/test/visitor")
    def whoami(visitor: CurrentVisitor) -> dict[str, str]:
        return {"visitor_id": str(visitor.visitor_id)}

    return TestClient(app)


@pytest.fixture
def visitor_client(settings: Settings) -> Iterator[TestClient]:
    with make_client(settings) as client:
        yield client


def visitor_count(client: TestClient) -> int:
    with Session(client.app.state.engine) as session:
        return session.exec(select(func.count()).select_from(Visitor)).one()


def test_first_visit_creates_visitor_and_sets_cookie(visitor_client):
    response = visitor_client.get("/test/visitor")

    visitor_id = response.json()["visitor_id"]
    assert UUID(visitor_id)
    assert response.cookies[VISITOR_COOKIE] == visitor_id
    assert visitor_count(visitor_client) == 1


def test_cookie_attributes(visitor_client):
    header = visitor_client.get("/test/visitor").headers["set-cookie"]

    assert "HttpOnly" in header
    assert "SameSite=lax" in header
    assert f"Max-Age={COOKIE_MAX_AGE_S}" in header
    assert "Secure" not in header  # plain http in tests


def test_returning_visitor_is_recognised(visitor_client):
    first = visitor_client.get("/test/visitor").json()["visitor_id"]
    second = visitor_client.get("/test/visitor").json()["visitor_id"]

    assert first == second
    assert visitor_count(visitor_client) == 1


@pytest.mark.parametrize("cookie", ["garbage", "", "1234"])
def test_invalid_cookie_is_replaced(visitor_client, cookie):
    visitor_client.cookies.set(VISITOR_COOKIE, cookie)

    response = visitor_client.get("/test/visitor")

    assert UUID(response.json()["visitor_id"])
    assert response.cookies[VISITOR_COOKIE] != cookie


def test_unknown_but_valid_id_gets_a_new_visitor(visitor_client):
    unknown = str(uuid4())
    visitor_client.cookies.set(VISITOR_COOKIE, unknown)

    response = visitor_client.get("/test/visitor")

    assert response.json()["visitor_id"] != unknown
    assert visitor_count(visitor_client) == 1


def test_cookie_is_secure_behind_https(tmp_path):
    settings = Settings(database_path=tmp_path / "t.db", public_base_url="https://example.org")

    with make_client(settings) as client:
        header = client.get("/test/visitor").headers["set-cookie"]

    assert "Secure" in header


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("not-a-uuid", None),
        ("6f1c1d0e-6a7b-4d8e-9f00-0a1b2c3d4e5f", UUID("6f1c1d0e-6a7b-4d8e-9f00-0a1b2c3d4e5f")),
    ],
)
def test_parse_visitor_id(raw, expected):
    assert parse_visitor_id(raw) == expected
