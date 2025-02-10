from pydantic import BaseModel
from typing import Optional

class TransactionBase(BaseModel):
    description: str
    amount: float
    type: str  # "income" eller "expense"

class TransactionCreate(TransactionBase):
    pass

class Transaction(TransactionBase):
    id: int

    class Config:
        from_attributes = True
