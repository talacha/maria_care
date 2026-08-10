from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.loop import run_chat
from app.db import get_db
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    try:
        conversation_id, message, refused = run_chat(
            db,
            message=payload.message,
            conversation_id=payload.conversation_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Chat agent failed: {exc}") from exc

    return ChatResponse(
        conversation_id=conversation_id,
        message=message,
        refused=refused,
    )
