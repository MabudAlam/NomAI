from fastapi import APIRouter, Query

from app.models.diet_model import DietInput, SuggestAlternateRequest, NutritionResponseModel
from app.models.service_response import NutritionServiceResponse
from app.services.diet_service import DietService


router = APIRouter()


@router.post("", response_model=NutritionServiceResponse)
def create_weekly_diet(diet_input: DietInput) -> NutritionServiceResponse:
    """
    Generate a new weekly diet plan based on user input.

    Args:
        diet_input: User's dietary requirements and preferences

    Returns:
        NutritionServiceResponse containing the generated WeeklyDietOutput
    """
    return DietService.generate_weekly_diet(diet_input)


@router.get("/{user_id}", response_model=NutritionServiceResponse)
def get_weekly_diet(user_id: str) -> NutritionServiceResponse:
    """
    Get the active weekly diet for a user.

    Args:
        user_id: The user ID

    Returns:
        NutritionServiceResponse containing the active WeeklyDietOutput
    """
    diet = DietService.get_active_diet(user_id)
    if diet is None:
        return NutritionServiceResponse(
            response=None,
            status=404,
            message="No active diet found for this user",
            metadata=None,
        )
    return NutritionServiceResponse(
        response=diet,
        status=200,
        message="SUCCESS",
        metadata=None,
    )


@router.get("/{user_id}/history", response_model=NutritionServiceResponse)
def get_diet_history(
    user_id: str,
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> NutritionServiceResponse:
    """
    Get diet history for a user.

    Args:
        user_id: The user ID
        limit: Maximum number of diets to return (1-50)
        offset: Number of diets to skip

    Returns:
        NutritionServiceResponse containing list of past WeeklyDietOutput
    """
    diets, total = DietService.get_diet_history(user_id, limit, offset)
    return NutritionServiceResponse(
        response={"diets": diets, "total": total, "limit": limit, "offset": offset},
        status=200,
        message="SUCCESS",
        metadata=None,
    )


@router.post("/{user_id}/suggest-alternatives", response_model=NutritionServiceResponse)
def suggest_alternate_meals(
    user_id: str,
    request: SuggestAlternateRequest,
) -> NutritionServiceResponse:
    """
    Suggest 5 alternative meals for a specific food item.

    Args:
        user_id: The user ID
        request: The alternate meal request details

    Returns:
        NutritionServiceResponse containing 5 alternative NutritionResponseModel
    """
    return DietService.suggest_alternatives(user_id, request)


@router.put("/{user_id}/{day_index}/meals/{meal_type}", response_model=NutritionServiceResponse)
def update_meal(
    user_id: str,
    day_index: int,
    meal_type: str,
    new_meal: NutritionResponseModel,
) -> NutritionServiceResponse:
    """
    Update a specific meal in the active diet.

    Args:
        user_id: The user ID
        day_index: Day index (0-6)
        meal_type: Type of meal (breakfast, lunch, dinner, snack)
        new_meal: New meal data

    Returns:
        NutritionServiceResponse with success status
    """
    success = DietService.update_meal(user_id, day_index, meal_type, new_meal)
    if not success:
        return NutritionServiceResponse(
            response=None,
            status=404,
            message="Failed to update meal. No active diet found.",
            metadata=None,
        )
    return NutritionServiceResponse(
        response={"updated": True},
        status=200,
        message="SUCCESS",
        metadata=None,
    )


@router.get("/{user_id}/diet/{diet_id}", response_model=NutritionServiceResponse)
def get_diet_by_id(
    user_id: str,
    diet_id: str,
) -> NutritionServiceResponse:
    """
    Get a specific diet by its ID.

    Args:
        user_id: The user ID
        diet_id: The diet document ID

    Returns:
        NutritionServiceResponse containing the WeeklyDietOutput
    """
    diet = DietService.get_diet_by_id(user_id, diet_id)
    if diet is None:
        return NutritionServiceResponse(
            response=None,
            status=404,
            message="Diet not found",
            metadata=None,
        )
    return NutritionServiceResponse(
        response=diet,
        status=200,
        message="SUCCESS",
        metadata=None,
    )


@router.post("/{user_id}/diet/{diet_id}/copy", response_model=NutritionServiceResponse)
def copy_diet(
    user_id: str,
    diet_id: str,
) -> NutritionServiceResponse:
    """
    Copy a past diet as a new active diet.

    This will mark all current active diets as completed and create a copy of the
    specified diet as the new active diet.

    Args:
        user_id: The user ID
        diet_id: The diet document ID to copy

    Returns:
        NutritionServiceResponse containing the new WeeklyDietOutput
    """
    result = DietService.copy_diet(user_id, diet_id)
    if result is None:
        return NutritionServiceResponse(
            response=None,
            status=404,
            message="Diet not found",
            metadata=None,
        )
    new_diet, execution_time = result
    return NutritionServiceResponse(
        response=new_diet,
        status=200,
        message="SUCCESS",
        metadata=None,
    )
