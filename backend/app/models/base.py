from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> Column:
    return Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def auto_uuid() -> Column:
    return Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=new_uuid,
        server_default=func.gen_random_uuid(),
    )
