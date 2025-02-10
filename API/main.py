from fastapi import FastAPI
from API.routers import budget
from API.database import engine
from API.models import Base

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(budget.router)

@app.get("/")
def root():
    return {"message": "Welcome to BudgetBuddy API"}
