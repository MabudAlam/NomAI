from typing import Literal, Optional, Dict, Any, List
from pydantic import BaseModel
from typing_extensions import TypedDict


class ChatMessage(TypedDict):
    """Simplified format of chat messages stored in Firestore."""

    role: Literal["user", "model", "assistant"]
    text: str
    sources: Optional[Dict[str, Any]]
    timestamp: str


class SendMessageRequest(BaseModel):
    """Request model for sending a chat message."""

    text: str
    user_id: str
    local_time: Optional[str] = None
    dietary_preferences: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    selected_goals: Optional[List[str]] = None
    image_url: Optional[str] = None
    image_data: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = None


class GetMessagesResponse(TypedDict):
    """Response model for getting chat messages."""

    messages: List[ChatMessage]
    total: int
    offset: int
    limit: int
