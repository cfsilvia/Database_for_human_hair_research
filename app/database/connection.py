from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True,)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False,)

def test_connection():
     with engine.connect() as connection:
           result = connection.execute(text("SELECT current_database(), current_user"))
           
     return result.fetchone()