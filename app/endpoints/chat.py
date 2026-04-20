from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models.chat_models import GetMessagesResponse, SendMessageRequest, UpdateLogStatusRequest
from app.services.chat_firestore import chat_firestore
from app.utils.error_handler import ErrorHandler
from app.exceptions import BaseNomAIException

router = APIRouter()


@router.get(
    "",
    response_model=GetMessagesResponse,
    description="Get chat messages for a user with pagination.",
)
async def get_chat_messages(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
) -> JSONResponse:
    """
    Get chat messages for a user.

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


@router.patch(
    "/log-status",
    description="Update the isAddedToLogs flag for a chat message.",
)
async def update_message_log_status(payload: UpdateLogStatusRequest) -> JSONResponse:
    """
    Update the log status for a specific message.

    Args:
        payload: Contains user_id, message_id, and is_added_to_logs

    Returns:
        JSONResponse with success status
    """
    try:
        success = chat_firestore.update_message_log_status(
            user_id=payload.user_id,
            message_id=payload.message_id,
            is_added_to_logs=payload.is_added_to_logs,
        )

        if success:
            return JSONResponse(
                content={"success": True, "message": "Log status updated"},
                status_code=200
            )
        else:
            return JSONResponse(
                content={"success": False, "error": "Message not found"},
                status_code=404
            )

    except BaseNomAIException as e:
        error_response = ErrorHandler.handle_custom_exception(exception=e)
        return JSONResponse(
            status_code=error_response.status_code,
            content=error_response.to_dict()
        )

    except Exception as e:
        error_response = ErrorHandler.handle_unexpected_exception(
            exception=e,
            user_message="Failed to update log status"
        )
        return JSONResponse(
            status_code=error_response.status_code,
            content=error_response.to_dict()
        )
