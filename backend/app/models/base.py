from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


def utcnow() -> Column:
    return Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def auto_uuid():
    from sqlalchemy import Column
    from sqlalchemy.dialects.postgresql import UUID
    return Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
        server_default=func.gen_random_uuid(),
    )
