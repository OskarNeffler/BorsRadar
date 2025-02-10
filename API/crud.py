from sqlalchemy.orm import Session
from API import models, schemas

def create_budget(db: Session, budget: schemas.BudgetCreate):
    db_budget = models.Budget(name=budget.name, amount=budget.amount)
    db.add(db_budget)
    db.commit()
    db.refresh(db_budget)
    return db_budget

def get_budgets(db: Session):
    return db.query(models.Budget).all()
