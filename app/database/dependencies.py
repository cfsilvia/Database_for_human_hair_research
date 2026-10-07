from app.database.connection import SessionLocal
'''
this function is important when multiple computers/users
computer A -- database session A
computer B -- database session B
'''

def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()