from sqlalchemy import Column, Integer, String, Float, ForeignKey
from .db import Base


# ---------------- DOCUMENTS ----------------
class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    url = Column(String)
    source_domain = Column(String)
    title = Column(String)
    published_date = Column(String)
    credibility = Column(Float)


# ---------------- STATEMENTS ----------------
class Statement(Base):
    __tablename__ = "statements"

    id = Column(Integer, primary_key=True)
    actor = Column(String)
    target = Column(String)
    action = Column(String)
    tone = Column(Float)
    document_id = Column(Integer, ForeignKey("documents.id"))
    timestamp = Column(String)


# ---------------- EVENTS (GDELT) ----------------
class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    actor1 = Column(String)
    actor2 = Column(String)
    event_type = Column(String)
    intensity = Column(Float)
    event_date = Column(String)
    source = Column(String)

