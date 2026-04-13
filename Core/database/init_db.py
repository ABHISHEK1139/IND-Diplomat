from .db import engine
from .models import Base


def init_database():
    Base.metadata.create_all(bind=engine)
    print("Database created successfully!")


if __name__ == "__main__":
    init_database()

