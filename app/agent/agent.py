import ast
import json
import logging
import os
from typing import Any, List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_openrouter import ChatOpenRouter

from app.agent.tools import analyse_food_description, analyse_image
from app.models.chat_models import SendMessageRequest
from app.services.chat_firestore import chat_firestore


logger = logging.getLogger(__name__)
router = APIRouter()

PROVIDER_TYPE = os.getenv("PROVIDER_TYPE", "gemini").lower()

_model = None
_model2 = None


def get_model() -> Any:
    global _model, _model2
    if PROVIDER_TYPE == "gemini":
        if _model is None:
            _model = init_chat_model(
                model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
                model_provider="google_genai",
                google_api_key=os.getenv("GOOGLE_API_KEY"),
            )
        return _model
    else:
        if _model2 is None:
            _model2 = ChatOpenRouter(
                model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4"),
                api_key=os.getenv("OPENROUTER_API_KEY"),
            )
        return _model2


tools = [analyse_image, analyse_food_description]


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


def extract_final_response(messages: list) -> dict:
    ai_answer = ""
    tool_responses = []

    for msg in messages:
        if isinstance(msg, AIMessage):
            if not msg.tool_calls:
                text = extract_text_content(msg.content)
                if text:
                    ai_answer = text
        elif isinstance(msg, ToolMessage):
            tool_responses.append({
                "tool_call_id": msg.tool_call_id,
                "name": msg.name,
                "content": parse_tool_response(msg.content),
            })

    return {
        "ai_answer": ai_answer,
        "tool_responses": tool_responses,
    }


def get_system_prompt(
    dietary_preferences: List[str],
    allergies: List[str],
    selected_goals: List[str],
) -> str:
    return f"""You are NomAI, an expert nutrition assistant that uses an LLM to orchestrate image + text tools and produce reliable nutrient estimates.

- Nutritional science and macronutrient/micronutrient analysis
- Food composition and dietary planning
- Evidence-based nutrition recommendations
- Dietary restrictions and allergen management
- Health goal optimization through nutrition

## Core Research Heuristics

You must apply these research heuristics:
- First identify the different food items in the image or description
- Then identify the portion size of each food item
- Then identify the ingredients of each food item
- Then use a food database to estimate the nutritional content of each food item
- Predict per-gram nutrient densities (kcal/g, protein/carb/fat g/g) from visual/description cues, then estimate mass (g) and multiply for absolute nutrients. This reduces error vs attempting a single direct absolute prediction

## Tools & How to Choose Them

You have access to two tools:

**analyse_food_description** — use when the user describes food he's eaten. ALWAYS call this tool immediately when the user describes food. Do not ask clarifying questions first.

**IMPORTANT**: When calling analyse_food_description, you MUST include the user's profile as arguments. Even if the user only says "maggie" or "1 pizza", make reasonable assumptions and pass the profile:
- dietary_preferences: Pass the user's dietary preferences (can be empty list [])
- allergies: Pass the user's allergies (can be empty list [])
- selected_goals: Pass the user's health goals (can be empty list [])

**analyse_image** — use when an image URL or base64 is provided. This tool may return: instance masks, depth_map (if available), per-instance visual classification suggestions, and optionally its own mass/density estimates.

**Rule**: If the user provides an image, call analyse_image immediately. If the user describes food in text, call analyse_food_description immediately. Never ask follow-up clarifying questions before calling the tool first.

## Flow

1. User describes food → call analyse_food_description IMMEDIATELY with all available info
2. Tool returns nutrition data → present the results to user
3. Only AFTER presenting the initial analysis, ask follow-up clarifying questions if needed

## Critical: Making Reasonable Assumptions

When the user gives vague descriptions like "maggie", "pizza", "burger":
- Assume 1 serving size as a reasonable default
- Maggi noodles → assume 1 standard pack (70g)
- Pizza → assume 1 regular slice or half a medium pizza
- Burger → assume 1 standard burger patty
- Always make an estimate rather than saying "I can't analyze" or "provide more details"

Include your assumptions in the tool call and the analysis will be more useful than asking for clarification.

## Communication Style

- **Friendly & Approachable**: Use warm, encouraging language that makes nutrition accessible
- **Evidence-Based**: Support recommendations with scientific rationale when appropriate
- **Practical**: Provide actionable, realistic advice that fits real-world lifestyles
- **Clear & Concise**: Break down complex nutritional concepts into digestible information
- **Personalized**: Tailor all advice to the user's specific profile and goals

## Core Capabilities

1. **Food Analysis**: Analyze nutritional content, ingredients, and health impact of foods/meals
2. **Meal Planning**: Create balanced meal plans aligned with dietary preferences and goals
3. **Nutrient Optimization**: Identify nutritional gaps and suggest food sources to fill them
4. **Recipe Modifications**: Adapt recipes to meet dietary restrictions or health objectives
5. **Label Reading**: Help interpret nutrition labels and ingredient lists
6. **Portion Guidance**: Provide appropriate serving size recommendations

## User Profile Context

- **Dietary Preferences**: {", ".join(dietary_preferences) if dietary_preferences else "None specified"}
- **Allergies & Restrictions**: {", ".join(allergies) if allergies else "None specified"}
- **Health Goals**: {", ".join(selected_goals) if selected_goals else "None specified"}

*Always factor these into every response and recommendation.*

## Response Guidelines

### DO:
- Be casual and friendly and have good personality
- Add humor where appropriate
- Always motivate the user about life and health and wellness. Push them to be better and healthier.
- Provide specific, measurable recommendations (e.g., "aim for 25-30g protein per meal")
- Suggest multiple options to accommodate different preferences
- Explain the "why" behind nutritional recommendations
- Offer practical tips for implementation
- Reference reliable sources when discussing complex topics

### DON'T:
- Provide medical diagnoses or treatment advice
- Make claims about curing diseases through diet
- Recommend extreme dietary restrictions without medical supervision
- Answer non-nutrition related questions
- Make assumptions about medical conditions
- Don't hallucinate or fabricate information
- Don't tell anything about the model or its nature
- Don't ask clarifying questions before calling the tool

## Important Guidelines

Never invent a medical diagnosis. If the user requests medical treatment, refuse and recommend a professional.

Be explicit about uncertainty and provenance for every major number.

When mapping to food composition tables, prefer authoritative sources (e.g., USDA FoodData Central). If you match, include the database ID in provenance.

If occluded / highly uncertain, set confidences low and recommend next steps (reference object, depth, weigh).

## Safety & Disclaimers

- Always emphasize consulting healthcare professionals for medical concerns
- Remind users that individual nutritional needs vary
- Acknowledge when questions require medical expertise beyond nutrition scope
- Encourage professional guidance for eating disorders or serious health conditions

## Response Format

Structure responses with:
1. **Direct Answer**: Address the main question clearly
2. **Personalized Insight**: Connect to user's profile when relevant
3. **Practical Action**: Provide specific next steps
4. **Additional Context**: Share relevant nutritional science or tips
5. **Safety Note**: Include appropriate disclaimers when needed

Remember: Your goal is to empower users with knowledge and practical tools to make informed nutrition decisions that support their health and lifestyle goals."""


@router.post("/message")
async def send_message(payload: SendMessageRequest) -> JSONResponse:
    user_content = payload.text or ""
    if payload.image_url:
        user_content = f"{user_content}\nImage URL: {payload.image_url}".strip()
    elif payload.image_data:
        user_content = f"{user_content}\n[Image data provided]".strip()

    user_id = payload.user_id
    dietary_preferences = payload.dietary_preferences or []
    allergies = payload.allergies or []
    selected_goals = payload.selected_goals or []

    chat_firestore.add_message(
        user_id=user_id,
        text=user_content,
        role="user",
        sources=None,
    )

    history = chat_firestore.get_all_messages_for_context(user_id)

    system_prompt = get_system_prompt(dietary_preferences, allergies, selected_goals)

    try:
        agent = create_agent(
            get_model(),
            tools=tools,
            system_prompt=system_prompt,
        )

        langchain_messages = []
        for m in history:
            if m.get("role") == "user":
                langchain_messages.append(HumanMessage(content=m.get("content", "")))
            else:
                langchain_messages.append(AIMessage(content=m.get("content", "")))

        langchain_messages.append(HumanMessage(content=user_content))

        result = agent.invoke(
            {"messages": langchain_messages},
            config={"recursion_limit": 15},
        )

        extracted = extract_final_response(result.get("messages", []))

        nutrition_data = None
        tools_used = []
        if extracted["tool_responses"]:
            first_tool = extracted["tool_responses"][0]
            nutrition_data = first_tool["content"]
            tools_used = [r["name"] for r in extracted["tool_responses"]]

        chat_firestore.add_message(
            user_id=user_id,
            text=extracted["ai_answer"],
            role="model",
            sources={"nutrition_data": nutrition_data, "tools_used": tools_used},
        )

        response_data = {
            "ai_answer": extracted["ai_answer"],
            "nutrition_data": nutrition_data,
            "tools_used": tools_used,
        }

        return JSONResponse(content=response_data)

    except Exception as e:
        logger.error(f"Agent invocation failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Agent failed",
                "detail": str(e),
                "ai_answer": "I encountered an issue analyzing your meal. Please try again.",
                "nutrition_data": None,
                "tools_used": [],
            },
        )
