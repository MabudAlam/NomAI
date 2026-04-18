from typing import List

from langgraph.graph import add_messages
from typing_extensions import Annotated

from dataclasses import dataclass, field

from langchain_core.messages import AnyMessage


@dataclass
class State:
    """Full agent state."""

    text: str = ""
    messages: Annotated[list[AnyMessage], add_messages] = field(default_factory=list)
    user_id: str = ""
    local_time: str = ""
    dietary_preferences: List[str] = field(default_factory=list)
    allergies: List[str] = field(default_factory=list)
    selected_goals: List[str] = field(default_factory=list)
    image_url: str = ""