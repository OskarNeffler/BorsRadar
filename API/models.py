from pydantic import BaseModel

class Budget(BaseModel):
    income: float
    expenses: float
