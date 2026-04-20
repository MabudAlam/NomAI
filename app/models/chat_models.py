from typing import Literal, Optional, Dict, Any, List
from pydantic import BaseModel
from typing_extensions import TypedDict


class ChatMessage(TypedDict):
    """Simplified format of chat messages stored in Firestore."""

    messageId: str
    role: Literal["user", "model", "assistant"]
    text: str
    image_url: Optional[str]
    sources: Optional[Dict[str, Any]]
    isAddedToLogs: bool
    timestamp: str


class SendMessageRequest(BaseModel):
    """Request model for sending a chat message."""

    text: str
    user_id: str
    local_message_id: Optional[str] = None  # Client-generated unique ID
    local_time: Optional[str] = None
    dietary_preferences: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    selected_goals: Optional[List[str]] = None
    image_url: Optional[str] = None
    image_data: Optional[str] = None


class UpdateLogStatusRequest(BaseModel):
    """Request model for updating message log status."""

    user_id: str
    message_id: str
    is_added_to_logs: bool


class GetMessagesResponse(TypedDict):
    """Response model for getting chat messages."""

    messages: List[ChatMessage]
    total: int
    offset: int
    limit: int
