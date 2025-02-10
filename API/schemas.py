from pydantic import BaseModel

class BudgetSchema(BaseModel):
    income: float
    expenses: float
    balance: float
