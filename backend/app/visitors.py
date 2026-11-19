"""Pseudonymous visitor identity via a random ID in a cookie. No login, no personal data."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request, Response
from sqlmodel import Session

from app.db import get_session
from app.models import Visitor

VISITOR_COOKIE = "nc_visitor"
COOKIE_MAX_AGE_S = 365 * 24 * 60 * 60


def parse_visitor_id(raw: str | None) -> UUID | None:
    """Return the visitor ID from a cookie value, or None if it is missing or not a UUID."""
    if not raw:
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


def get_visitor(
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> Visitor:
    """FastAPI dependency: the current visitor, created on the first visit.

    The cookie is (re)set on every request, so the one-year expiry slides with each visit.
    It only reaches the client if the endpoint returns data. If an endpoint returns its own
    `Response` (e.g. a template), FastAPI drops the cookie. Pages therefore call the JSON API.
    """
    visitor_id = parse_visitor_id(request.cookies.get(VISITOR_COOKIE))
    visitor = session.get(Visitor, visitor_id) if visitor_id else None

    if visitor is None:
        visitor = Visitor()
        session.add(visitor)
        session.commit()
        session.refresh(visitor)

    response.set_cookie(
        VISITOR_COOKIE,
        str(visitor.visitor_id),
        max_age=COOKIE_MAX_AGE_S,
        httponly=True,
        samesite="lax",
        secure=request.app.state.settings.cookies_secure,
    )
    return visitor


CurrentVisitor = Annotated[Visitor, Depends(get_visitor)]
