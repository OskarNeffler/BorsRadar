from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import budget

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(budget.router)

@app.get("/")
def root():
    return {"message": "Welcome to BudgetBuddy API"}
