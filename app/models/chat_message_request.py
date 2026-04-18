from typing import List, Optional
from pydantic import BaseModel


class SendMessageRequest(BaseModel):
    """Request model for sending a chat message."""

    text: str
    user_id: str
    local_time: Optional[str] = None
    dietary_preferences: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    selected_goals: Optional[List[str]] = None
    foodImage: Optional[str] = None



