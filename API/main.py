from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import engine, SessionLocal
from models import Base
from schemas import TransactionCreate, Transaction
import crud

# Skapa databastabeller
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Dependency för att hantera databassession
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/transactions/", response_model=Transaction)
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db)):
    return crud.create_transaction(db, transaction)

@app.get("/transactions/", response_model=list[Transaction])
def read_transactions(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    return crud.get_transactions(db, skip=skip, limit=limit)

@app.get("/")
def read_root():
    return {"message": "Welcome to BudgetBuddy API"}
