from typing import Optional

from langchain.tools import tool
from langgraph.prebuilt import ToolNode
from app.models.nutrition_input_payload import NutritionInputPayload
from app.models.service_response import NutritionServiceResponse
from app.services.nutrition_service import NutritionService


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

    payload = NutritionInputPayload(
        imageData=image_data,
        imageUrl=image_url,
        food_description=food_description or "",
        dietaryPreferences=dietary_preferences or [],
        allergies=allergies or [],
        selectedGoals=selected_goals or [],
    )

    response = NutritionService.get_nutrition_data(query=payload)
    return response.model_dump() if hasattr(response, "model_dump") else response


@tool
def analyse_food_description(
    food_description: str,
    image_data: Optional[str] = None,
    image_url: Optional[str] = None,
    dietary_preferences: Optional[list[str]] = None,
    allergies: Optional[list[str]] = None,
    selected_goals: Optional[list[str]] = None,
    exa_results: Optional[list[dict]] = None,
) -> dict:
    """
    Analyze food from text description to extract nutrition information. Use this tool when user describes food in text format (no image).

    Args:
        food_description: Description of the food item (required)
        image_data: Base64 encoded image data (optional - for combined analysis)
        image_url: URL of an image (optional - for combined analysis)
        dietary_preferences: User's dietary preferences
        allergies: User's food allergies
        selected_goals: User's health goals
        exa_results: Optional web search results from EXA for enhanced analysis
    Returns:
        dict: Structured response with nutrition data
    """
    payload = NutritionInputPayload(
        food_description=food_description,
        imageData=image_data,
        imageUrl=image_url,
        dietaryPreferences=dietary_preferences or [],
        allergies=allergies or [],
        selectedGoals=selected_goals or [],
    )

    response = NutritionService.log_food_nutrition_data_using_description(
        payload, exa_results=exa_results
    )
    return response.model_dump() if hasattr(response, "model_dump") else response
