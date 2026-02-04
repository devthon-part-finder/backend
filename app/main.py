import email
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from .database import SessionLocal, engine
from sqlalchemy import text
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

def get_db():
    db = SessionLocal()
    logger.info("Database connection established")
    try:
        yield db
    finally:
        db.close()
        logger.info("Database connection closed")

@app.get("/")
def root():
    return {"message": "Hello FastAPI!!!"}

# @app.get("/users")
# def get_users(db: Session = Depends(get_db)):
#     query = text("SELECT id, username, email FROM users")
#     result = db.execute(query)
#     users = [{"id": row[0], "username": row[1], "email": row[2]} for row in result]
#     return users




