from fastapi import APIRouter

router = APIRouter(prefix="/budget", tags=["Budget"])

@router.get("/")
def get_budget():
    return {"message": "Budget data endpoint"}
