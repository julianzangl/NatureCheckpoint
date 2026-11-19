"""Request and response models of the REST API (see the contracts in docs/architecture.md)."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
