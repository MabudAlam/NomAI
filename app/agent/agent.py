import ast
import json
import logging
import re
from typing import Any, List, Union

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from app.agent.graph import build_graph
from app.models.chat_models import SendMessageRequest


logger = logging.getLogger(__name__)
router = APIRouter()


def extract_text_content(content: Any) -> str:
    """Extract clean text from message content that can be string or list of blocks."""
    if not content:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "image":
                    text_parts.append("[image]")
            elif isinstance(block, str):
                text_parts.append(block)
        return " ".join(text_parts)
    return str(content)


def parse_tool_response(tool_response: Any) -> Any:
    """Parse tool response string into proper JSON dict."""
    if isinstance(tool_response, dict):
        return tool_response
    if isinstance(tool_response, str):
        try:
            return json.loads(tool_response)
        except json.JSONDecodeError:
            try:
                return ast.literal_eval(tool_response)
            except (ValueError, SyntaxError):
                return {"raw": tool_response}
    return tool_response


@router.post("/message")
async def send_message(payload: SendMessageRequest) -> JSONResponse:
    graph = build_graph()

    user_content = payload.text or ""
    if payload.image_url:
        user_content = f"{user_content}\nImage URL: {payload.image_url}".strip()
    elif payload.image_data:
        user_content = f"{user_content}\n[Image data provided]".strip()

    initial_state = {
        "text": payload.text or "",
        "user_id": payload.user_id or "",
        "local_time": payload.local_time or "",
        "dietary_preferences": payload.dietary_preferences or [],
        "allergies": payload.allergies or [],
        "selected_goals": payload.selected_goals or [],
        "image_url": payload.image_url or "",
        "messages": [HumanMessage(content=user_content)],
    }

    result = graph.invoke(initial_state)

    messages = result.get("messages", [])
    ai_answer = ""
    tool_response = None

    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            if not ai_answer:
                ai_answer = extract_text_content(msg.content)
        elif isinstance(msg, ToolMessage):
            if tool_response is None:
                tool_response = msg.content

    if tool_response:
        tool_response = parse_tool_response(tool_response)
        if not ai_answer:
            ai_answer = tool_response

    response_data = {
        "ai_answer": ai_answer,
        "tool_response": tool_response,
    }

    return JSONResponse(content=response_data)
