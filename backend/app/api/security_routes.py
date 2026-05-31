
from fastapi import APIRouter
from app.security.jwt_manager import JWTManager

router = APIRouter()

jwt_manager = JWTManager()

@router.post("/auth/token")
async def create_token(payload: dict):

    user_id = payload.get("user_id", "anonymous")

    token = jwt_manager.generate_token(user_id)

    return {
        "token": token
    }
