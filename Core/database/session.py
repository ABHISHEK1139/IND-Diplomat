from .db import SessionLocal


def get_session():
    return SessionLocal()

