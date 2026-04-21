from typing import List, Optional
from pydantic import BaseModel, Field
from app.models.nutrition_output_payload import NutritionResponseModel, Portion


class DietInput(BaseModel):
    userId: str = Field(..., description="Unique identifier for the user")
    calories: int = Field(..., description="Target daily calories")
    protein: int = Field(..., description="Target daily protein (grams)")
    carbs: int = Field(..., description="Target daily carbs (grams)")
    fiber: int = Field(..., description="Target daily fiber (grams)")
    fat: int = Field(..., description="Target daily fat (grams)")
    dietaryPreferences: List[str] = Field(
        default_factory=list, description="User's dietary preferences"
    )
    allergies: List[str] = Field(
        default_factory=list, description="User's food allergies"
    )
    selectedGoals: List[str] = Field(
        default_factory=list, description="User's health goals"
    )
    dislikedFoods: List[str] = Field(
        default_factory=list, description="Foods the user dislikes"
    )
    anyDiseases: List[str] = Field(
        default_factory=list, description="Any diseases the user has"
    )
    prompt: str = Field(
        ..., description="Additional prompt or instructions for the diet plan"
    )


class NutritionSummary(BaseModel):
    calories: int = Field(..., description="Total calories")
    protein: int = Field(..., description="Total protein (grams)")
    carbs: int = Field(..., description="Total carbs (grams)")
    fiber: int = Field(..., description="Total fiber (grams)")
    fat: int = Field(..., description="Total fat (grams)")


class MealsStructure(BaseModel):
    breakfast: NutritionResponseModel = Field(
        ..., description="Breakfast meal with full nutrition data"
    )
    lunch: NutritionResponseModel = Field(
        ..., description="Lunch meal with full nutrition data"
    )
    dinner: NutritionResponseModel = Field(
        ..., description="Dinner meal with full nutrition data"
    )
    snacks: List[NutritionResponseModel] = Field(
        default_factory=list, description="Snack items with full nutrition data"
    )


class DailyDietEntry(BaseModel):
    dayIndex: int = Field(..., ge=0, le=6, description="Day index 0-6")
    dayName: str = Field(..., description="Day name (Monday-Sunday)")
    meals: MealsStructure = Field(..., description="All meals for the day")
    totalNutrition: NutritionSummary = Field(
        ..., description="Daily nutrition totals"
    )
    cheatMealOfTheDay: Optional[NutritionResponseModel] = Field(
        None, description="Cheat meal suggestion for the day"
    )


class WeeklyDietOutput(BaseModel):
    dietId: Optional[str] = Field(None, description="Diet document ID (auto-generated)")
    userId: str = Field(..., description="User identifier")
    weekStartDate: str = Field(..., description="Week start date")
    weekEndDate: str = Field(..., description="Week end date")
    status: str = Field(
        default="active", description="Status: active, completed, modified"
    )
    dailyDiets: List[DailyDietEntry] = Field(
        ..., description="7 days of diet entries"
    )
    totalWeeklyNutrition: NutritionSummary = Field(
        ..., description="Aggregated weekly nutrition totals"
    )
    createdAt: Optional[str] = Field(None, description="Creation timestamp")
    updatedAt: Optional[str] = Field(None, description="Last update timestamp")


class WeeklyDietGenerationSchema(BaseModel):
    dailyDiets: List[DailyDietEntry] = Field(
        ..., description="7 days of diet entries for the week"
    )


class DailyDietGenerationSchema(BaseModel):
    """Schema for generating a single day's diet"""
    dayIndex: int = Field(..., ge=0, le=6)
    dayName: str
    meals: MealsStructure
    totalNutrition: NutritionSummary
    cheatMealOfTheDay: Optional[NutritionResponseModel] = None


class SuggestAlternativesSchema(BaseModel):
    """Schema for LLM to return multiple alternatives"""
    alternatives: List[NutritionResponseModel] = Field(
        ..., description="List of 5 alternative meals"
    )


class SuggestAlternativesResponse(BaseModel):
    """Response model for suggesting multiple meal alternatives"""
    alternatives: List[NutritionResponseModel] = Field(
        ..., description="List of 5 alternative meals"
    )
    currentMeal: NutritionResponseModel = Field(
        ..., description="The original meal being replaced"
    )


class SuggestAlternateRequest(BaseModel):
    currentMeal: NutritionResponseModel = Field(
        ..., description="Current meal to replace"
    )
    mealType: str = Field(
        ..., description="Type of meal: breakfast, lunch, dinner, snack"
    )
    prompt: str = Field(
        ..., description="User's preference or request for the alternate meal"
    )
    dietaryPreferences: List[str] = Field(
        default_factory=list, description="User's dietary preferences"
    )
    allergies: List[str] = Field(
        default_factory=list, description="User's food allergies"
    )
    dislikedFoods: List[str] = Field(
        default_factory=list, description="Foods the user dislikes"
    )
    anyDiseases: List[str] = Field(
        default_factory=list, description="Any diseases the user has"
    )
    selectedGoals: List[str] = Field(
        default_factory=list, description="User's health goals"
    )


class MarkMealEatenRequest(BaseModel):
    """Request model for marking a meal as eaten."""
    day_index: int = Field(..., ge=0, le=6, description="Day index (0-6)")
    meal_type: str = Field(..., description="Type of meal: breakfast, lunch, dinner, snack")
    is_eaten: bool = Field(..., description="Whether the meal has been eaten")


class GroceryListItem(BaseModel):
    name: str = Field(..., description="Name of the grocery item")
    quantity: str = Field(..., description="Quantity needed")
    notes: str = Field(..., description="Additional notes or instructions")


class FoodItem(BaseModel):
    """Deprecated: Use NutritionResponseModel instead"""
    name: str = Field(..., description="Name of the food item")
    calories: int = Field(..., description="Calories in the food item")
    protein: int = Field(..., description="Protein content in grams")
    carbs: int = Field(..., description="Carbohydrate content in grams")
    fiber: int = Field(..., description="Fiber content in grams")
    typeOfMeal: str = Field(
        ..., description="Type of meal (breakfast, lunch, dinner, snack)"
    )
    fat: int = Field(..., description="Fat content in grams")
    portion: Portion = Field(..., description="Portion unit of the food item")


class DailyDietOutput(BaseModel):
    """Deprecated: Use DailyDietEntry instead"""
    breakfast: List[FoodItem] = Field(
        default_factory=list, description="List of breakfast food items"
    )
    lunch: List[FoodItem] = Field(default_factory=list, description="List of lunch food items")
    snacks: List[FoodItem] = Field(default_factory=list, description="List of snack food items")
    dinner: List[FoodItem] = Field(default_factory=list, description="List of dinner food items")
    groceryList: List[GroceryListItem] = Field(
        default_factory=list, description="Grocery list for the day"
    )
    totalCalories: int = Field(..., description="Total calories for the day")
    cheatMealOfTheDay: FoodItem = Field(..., description="Cheat meal suggestion for the day")


class SuggestedDifferentMealInput(BaseModel):
    """Deprecated: Use SuggestAlternateRequest instead"""
    mealPrompt: str = Field(..., description="Prompt describing the meal")
    currentMeal: FoodItem = Field(..., description="Current meal details")
    mealType: str = Field(
        ..., description="Type of meal (breakfast, lunch, dinner, snack)"
    )
    dietaryPreferences: List[str] = Field(
        default_factory=list, description="User's dietary preferences"
    )
    allergies: List[str] = Field(
        default_factory=list, description="User's food allergies"
    )
    dislikedFoods: List[str] = Field(
        default_factory=list, description="Foods the user dislikes"
    )
    anyDiseases: List[str] = Field(
        default_factory=list, description="Any diseases the user has"
    )
    selectedGoals: List[str] = Field(
        default_factory=list, description="User's health goals"
    )
