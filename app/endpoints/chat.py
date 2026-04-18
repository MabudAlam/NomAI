from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.models.chat_models import GetMessagesResponse
from app.services.chat_firestore import chat_firestore
from app.utils.error_handler import ErrorHandler
from app.exceptions import BaseNomAIException

router = APIRouter()


@router.get("/chats", response_model=GetMessagesResponse)
async def get_chats(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
) -> JSONResponse:
    """
    Get chat history for a user with pagination.

    Args:
        user_id: The user ID
        limit: Maximum number of messages to return (default 20)
        offset: Number of messages to skip (default 0)

    Returns:
        JSONResponse with messages, total count, offset, and limit
    """
    try:
        messages, total = chat_firestore.get_messages(
            user_id=user_id,
            offset=offset,
            limit=limit,
        )

        response = GetMessagesResponse(
            messages=messages,
            total=total,
            offset=offset,
            limit=limit,
        )

        return JSONResponse(content=response, status_code=200)

    except BaseNomAIException as e:
        error_response = ErrorHandler.handle_custom_exception(exception=e)
        return JSONResponse(
            status_code=error_response.status_code,
            content=error_response.to_dict()
        )

    except Exception as e:
        error_response = ErrorHandler.handle_unexpected_exception(
            exception=e,
            user_message="Failed to retrieve chat history"
        )
        return JSONResponse(
            status_code=error_response.status_code,
            content=error_response.to_dict()
        )
