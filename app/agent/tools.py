import os
from typing import Optional

from langchain.tools import tool
from app.models.nutrition_input_payload import NutritionInputPayload
from app.models.service_response import NutritionServiceResponse
from app.services.nutrition_service_v2 import NutritionServiceV2, LLMProviderType


def _get_provider_from_env() -> LLMProviderType:
    provider_env = os.getenv("PROVIDER_TYPE", "")
    if provider_env.lower() == "openrouter":
        return LLMProviderType.OPENROUTER
    return LLMProviderType.GEMINI


@tool
def analyse_image(
    image_data: Optional[str] = None,
    image_url: Optional[str] = None,
    food_description: str = "",
    dietary_preferences: Optional[list[str]] = None,
    allergies: Optional[list[str]] = None,
    selected_goals: Optional[list[str]] = None,
) -> dict:
    """
    Analyze an image to extract nutrition information. Use this tool when user provides an image URL or base64 image data.

    IMPORTANT: At least one of image_url or image_data must be provided.

    Args:
        image_url: URL of the image for nutrition analysis
        image_data: Base64 encoded image data
        food_description: Text description of food (optional, for enhanced analysis)
        dietary_preferences: User's dietary preferences
        allergies: User's food allergies
        selected_goals: User's health goals
    Returns:
        dict: Structured response with nutrition data
    """
    if not image_url and not image_data:
        raise ValueError(
            "Either image_url or image_data must be provided for image analysis"
        )

    provider = _get_provider_from_env()

    payload = NutritionInputPayload(
        imageData=image_data,
        imageUrl=image_url,
        food_description=food_description or "",
        dietaryPreferences=dietary_preferences or [],
        allergies=allergies or [],
        selectedGoals=selected_goals or [],
    )

    response = NutritionServiceV2.get_nutrition_data(query=payload, provider_type=provider)
    return response.model_dump() if hasattr(response, "model_dump") else response


@tool
def analyse_food_description(
    food_description: str,
    image_data: Optional[str] = None,
    image_url: Optional[str] = None,
    dietary_preferences: Optional[list[str]] = None,
    allergies: Optional[list[str]] = None,
    selected_goals: Optional[list[str]] = None,
) -> dict:
    """
    Analyze food from text description to extract nutrition information. Use this tool when user describes food in text format (no image).

    IMPORTANT: You MUST include the user's profile context in every call:
    - Always pass dietary_preferences, allergies, and selected_goals from the user's profile
    - If the user says "I had maggie", include: dietary_preferences=["vegetarian"], allergies=["nuts"], selected_goals=["weight-loss"]
    - If you don't have the user's profile, make reasonable assumptions based on common preferences

    Never call this tool with only food_description alone. Always include the user's dietary context.

    Args:
        food_description: Description of the food item (e.g., "2 maggie noodles with veggies")
        dietary_preferences: User's dietary preferences (vegan, vegetarian, low-carb, etc.)
        allergies: User's food allergies (nuts, dairy, gluten, etc.)
        selected_goals: User's health goals (weight-loss, muscle-gain, maintenance, etc.)
    Returns:
        dict: Structured response with nutrition data
    """
    provider = _get_provider_from_env()

    payload = NutritionInputPayload(
        food_description=food_description,
        imageData=image_data,
        imageUrl=image_url,
        dietaryPreferences=dietary_preferences or [],
        allergies=allergies or [],
        selectedGoals=selected_goals or [],
    )

    response = NutritionServiceV2.log_food_nutrition_data_using_description(payload, provider_type=provider)
    return response.model_dump() if hasattr(response, "model_dump") else response
