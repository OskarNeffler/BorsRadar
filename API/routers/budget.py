from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from API import crud, schemas
from API.database import SessionLocal

router = APIRouter(prefix="/budgets", tags=["Budgets"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=schemas.Budget)
def create_budget(budget: schemas.BudgetCreate, db: Session = Depends(get_db)):
    return crud.create_budget(db=db, budget=budget)

@router.get("/", response_model=list[schemas.Budget])
def read_budgets(db: Session = Depends(get_db)):
    return crud.get_budgets(db=db)
