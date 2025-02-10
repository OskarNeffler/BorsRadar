from pydantic import BaseModel

class BudgetBase(BaseModel):
    name: str
    amount: float

class BudgetCreate(BudgetBase):
    pass

class Budget(BudgetBase):
    id: int

    class Config:
        orm_mode = True
