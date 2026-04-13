from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# This creates a local file database
DATABASE_URL = "sqlite:///ind_diplomat.db"

# engine = actual database connection
engine = create_engine(DATABASE_URL, echo=False)

# session = how we talk to DB
SessionLocal = sessionmaker(bind=engine)

# Base = parent class for all tables
Base = declarative_base()

