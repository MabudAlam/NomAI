import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List

from app.models.diet_model import (
    DietInput,
    WeeklyDietOutput,
    WeeklyDietGenerationSchema,
    DailyDietGenerationSchema,
    DailyDietEntry,
    SuggestAlternativesSchema,
    SuggestAlternativesResponse,
    NutritionSummary,
    SuggestAlternateRequest,
)
from app.models.nutrition_output_payload import NutritionResponseModel
from app.models.service_response import NutritionServiceResponse, ServiceMetadata
from app.services.diet_firestore import diet_firestore
from app.services.prompt_service import PromptService
from app.services.nutrition_service_v2 import (
    NutritionServiceV2,
    LLMProviderType,
)
from app.utils.token import calculate_cost


DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class DietService:
    """Service for weekly diet plan generation and management."""

    @classmethod
    def generate_weekly_diet(cls, diet_input: DietInput) -> NutritionServiceResponse:
        """
        Generate a weekly diet plan by generating each day individually.

        Args:
            diet_input: User's dietary requirements and preferences

        Returns:
            NutritionServiceResponse containing WeeklyDietOutput
        """
        start_time = time.time()

        import os
        provider_type = os.getenv("PROVIDER_TYPE", "gemini").lower()
        llm_provider = LLMProviderType.OPENROUTER if provider_type == "openrouter" else LLMProviderType.GEMINI
        provider = NutritionServiceV2._get_provider(llm_provider)

        daily_targets = cls._calculate_daily_targets(
            calories=diet_input.calories,
            protein=diet_input.protein,
            carbs=diet_input.carbs,
            fiber=diet_input.fiber,
            fat=diet_input.fat,
        )

        all_daily_diets: List[DailyDietEntry] = []
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0
        used_foods: List[str] = []

        for day_index, day_name in enumerate(DAY_NAMES):
            day_targets = daily_targets[day_index]

            prompt = PromptService.get_single_day_diet_prompt(
                diet_input=diet_input,
                day_name=day_name,
                day_index=day_index,
                daily_targets=day_targets,
                used_foods=used_foods,
            )

            result, input_t, output_t, total_t = provider.generate_from_text(
                prompt=prompt,
                response_schema=DailyDietGenerationSchema,
            )

            if result is None:
                raise Exception(f"Failed to generate diet for {day_name}")

            daily_diet = DailyDietEntry(
                dayIndex=result.dayIndex,
                dayName=result.dayName,
                meals=result.meals,
                totalNutrition=result.totalNutrition,
                cheatMealOfTheDay=result.cheatMealOfTheDay,
            )

            cls._clean_meal_data(daily_diet)
            all_daily_diets.append(daily_diet)

            cls._update_used_foods(used_foods, daily_diet)

            total_input_tokens += input_t
            total_output_tokens += output_t
            total_tokens += total_t

        total_weekly = cls._calculate_weekly_nutrition(all_daily_diets)

        weekly_diet = WeeklyDietOutput(
            userId=diet_input.userId,
            weekStartDate=cls._get_week_start(),
            weekEndDate=cls._get_week_end(),
            status="active",
            dailyDiets=all_daily_diets,
            totalWeeklyNutrition=total_weekly,
        )

        diet_id = diet_firestore.save(weekly_diet)
        weekly_diet.dietId = diet_id

        execution_time = time.time() - start_time

        return cls._build_response(
            response=weekly_diet,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            total_tokens=total_tokens,
            execution_time=execution_time,
        )

    @classmethod
    def get_active_diet(cls, user_id: str) -> Optional[WeeklyDietOutput]:
        """
        Get the active weekly diet for a user.

        Args:
            user_id: The user ID

        Returns:
            Active WeeklyDietOutput or None
        """
        result = diet_firestore.get_active(user_id)
        if result is None:
            return None
        diet_id, diet = result
        diet.dietId = diet_id
        return diet

    @classmethod
    def get_diet_history(
        cls, user_id: str, limit: int = 10, offset: int = 0
    ) -> Tuple[List[tuple], int]:
        """
        Get diet history for a user.

        Args:
            user_id: The user ID
            limit: Maximum number of diets to return
            offset: Number of diets to skip

        Returns:
            Tuple of (list of (diet_id, WeeklyDietOutput) tuples, total count)
        """
        return diet_firestore.get_history(user_id, limit, offset)

    @classmethod
    def get_diet_by_id(cls, user_id: str, diet_id: str) -> Optional[WeeklyDietOutput]:
        """
        Get a specific diet by its ID.

        Args:
            user_id: The user ID
            diet_id: The diet document ID

        Returns:
            WeeklyDietOutput or None
        """
        return diet_firestore.get_by_id(user_id, diet_id)

    @classmethod
    def copy_diet(cls, user_id: str, diet_id: str) -> Optional[tuple]:
        """
        Copy a past diet as a new active diet.

        Args:
            user_id: The user ID
            diet_id: The diet document ID to copy

        Returns:
            Tuple of (new WeeklyDietOutput, execution_time) or None if diet not found
        """
        start_time = time.time()

        old_diet = diet_firestore.get_by_id(user_id, diet_id)
        if old_diet is None:
            return None

        diet_firestore._mark_all_active_as_completed(user_id)

        new_diet = WeeklyDietOutput(
            userId=user_id,
            weekStartDate=cls._get_week_start(),
            weekEndDate=cls._get_week_end(),
            status="active",
            dailyDiets=old_diet.dailyDiets,
            totalWeeklyNutrition=old_diet.totalWeeklyNutrition,
        )

        new_diet_id = diet_firestore.save(new_diet)
        new_diet.dietId = new_diet_id

        execution_time = time.time() - start_time

        return new_diet, execution_time

    @classmethod
    def suggest_alternatives(
        cls, user_id: str, request: SuggestAlternateRequest
    ) -> NutritionServiceResponse:
        """
        Suggest 5 alternative meals for a specific food item.

        Args:
            user_id: The user ID
            request: The alternate meal request details

        Returns:
            NutritionServiceResponse containing SuggestAlternativesResponse with 5 alternatives
        """
        start_time = time.time()

        prompt = PromptService.get_suggest_alternate_prompt(request)

        import os
        provider_type = os.getenv("PROVIDER_TYPE", "gemini").lower()
        llm_provider = LLMProviderType.OPENROUTER if provider_type == "openrouter" else LLMProviderType.GEMINI
        provider = NutritionServiceV2._get_provider(llm_provider)

        result, input_tokens, output_tokens, total_tokens = provider.generate_from_text(
            prompt=prompt,
            response_schema=SuggestAlternativesSchema,
        )

        if result is None:
            raise Exception("Failed to generate alternate meals")

        response = SuggestAlternativesResponse(
            alternatives=result.alternatives,
            currentMeal=request.currentMeal,
        )

        execution_time = time.time() - start_time

        return cls._build_response(
            response=response.model_dump(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            execution_time=execution_time,
        )

    @classmethod
    def update_meal(
        cls,
        user_id: str,
        day_index: int,
        meal_type: str,
        new_meal: NutritionResponseModel,
    ) -> bool:
        """
        Update a specific meal in the active diet.

        Args:
            user_id: The user ID
            day_index: Day index (0-6)
            meal_type: Type of meal (breakfast, lunch, dinner, snack)
            new_meal: New meal data

        Returns:
            True if updated successfully
        """
        result = diet_firestore.get_active(user_id)
        if not result:
            return False

        diet_id, active_diet = result

        daily_diet = active_diet.dailyDiets[day_index]
        updated_meals = daily_diet.meals.model_copy()

        if meal_type == "breakfast":
            updated_meals.breakfast = new_meal
        elif meal_type == "lunch":
            updated_meals.lunch = new_meal
        elif meal_type == "dinner":
            updated_meals.dinner = new_meal
        elif meal_type == "snacks":
            snacks = list(updated_meals.snacks)
            if snacks:
                snacks[0] = new_meal
            else:
                snacks.append(new_meal)
            updated_meals.snacks = snacks

        daily_diet.meals = updated_meals

        return diet_firestore.update(user_id, diet_id, {"dailyDiets": active_diet.dailyDiets})

    @classmethod
    def _build_weekly_diet_output(
        cls, diet_input: DietInput, generation_result: WeeklyDietGenerationSchema
    ) -> WeeklyDietOutput:
        """Build WeeklyDietOutput from generation result."""
        total_weekly = cls._calculate_weekly_nutrition(generation_result.dailyDiets)

        return WeeklyDietOutput(
            userId=diet_input.userId,
            weekStartDate=cls._get_week_start(),
            weekEndDate=cls._get_week_end(),
            status="active",
            dailyDiets=generation_result.dailyDiets,
            totalWeeklyNutrition=total_weekly,
        )

    @classmethod
    def _calculate_weekly_nutrition(cls, daily_diets) -> NutritionSummary:
        """Calculate aggregated weekly nutrition totals."""
        totals = {"calories": 0, "protein": 0, "carbs": 0, "fiber": 0, "fat": 0}

        for day in daily_diets:
            totals["calories"] += day.totalNutrition.calories
            totals["protein"] += day.totalNutrition.protein
            totals["carbs"] += day.totalNutrition.carbs
            totals["fiber"] += day.totalNutrition.fiber
            totals["fat"] += day.totalNutrition.fat

        return NutritionSummary(**totals)

    @classmethod
    def _calculate_daily_targets(
        cls,
        calories: int,
        protein: int,
        carbs: int,
        fiber: int,
        fat: int,
    ) -> List[dict]:
        """Calculate daily macro targets with slight variation for each day.

        Distributes weekly targets across 7 days with subtle carb cycling:
        - 2 lower carb days (Mon, Thu) for metabolic variety
        - 3 moderate carb days (Tue, Wed, Sat)
        - 2 higher carb days (Fri, Sun) including a larger cheat meal
        """
        base_calories = calories
        base_protein = protein
        base_carbs = carbs
        base_fiber = fiber
        base_fat = fat

        carb_cycle_pattern = [0, -15, -10, -15, 10, -10, 15]

        daily_targets = []
        for i in range(7):
            carb_adj = carb_cycle_pattern[i]
            day_carbs = base_carbs + carb_adj

            day_calories = int(base_calories + (carb_adj * 4))
            day_protein = base_protein
            day_fat = base_fat
            day_fiber = base_fiber

            daily_targets.append({
                "calories": day_calories,
                "protein": day_protein,
                "carbs": day_carbs,
                "fiber": day_fiber,
                "fat": day_fat,
            })

        return daily_targets

    @classmethod
    def _update_used_foods(cls, used_foods: List[str], daily_diet: DailyDietEntry) -> None:
        """Extract food names and main ingredients from daily diet to track variety."""
        meals = daily_diet.meals
        meal_keys = ['breakfast', 'lunch', 'dinner', 'snacks']

        for meal_type in meal_keys:
            if meal_type == 'snacks':
                meal_items = meals.snacks or []
            else:
                meal_items = [getattr(meals, meal_type)] if hasattr(meals, meal_type) else []

            for meal in meal_items:
                if meal and hasattr(meal, 'ingredients'):
                    for ing in meal.ingredients:
                        food_name = ing.name.lower().strip()
                        if food_name and food_name not in used_foods:
                            used_foods.append(food_name)

        if daily_diet.cheatMealOfTheDay and hasattr(daily_diet.cheatMealOfTheDay, 'ingredients'):
            for ing in daily_diet.cheatMealOfTheDay.ingredients:
                food_name = ing.name.lower().strip()
                if food_name and food_name not in used_foods:
                    used_foods.append(food_name)

    @classmethod
    def _clean_meal_data(cls, daily_diet: DailyDietEntry) -> None:
        """Remove primaryConcerns and suggestAlternatives from all meals."""
        meals = daily_diet.meals
        meal_keys = ['breakfast', 'lunch', 'dinner', 'snacks']

        for meal_type in meal_keys:
            if meal_type == 'snacks':
                meal_items = meals.snacks or []
            else:
                meal_items = [getattr(meals, meal_type)] if hasattr(meals, meal_type) else []

            for meal in meal_items:
                if meal:
                    meal.primaryConcerns = []
                    meal.suggestAlternatives = []

        if daily_diet.cheatMealOfTheDay:
            daily_diet.cheatMealOfTheDay.primaryConcerns = []
            daily_diet.cheatMealOfTheDay.suggestAlternatives = []

    @classmethod
    def _get_week_start(cls) -> str:
        """Get current week's start date (Monday)."""
        today = datetime.now(timezone.utc)
        start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        days_since_monday = start.weekday()
        start = start - timedelta(days=days_since_monday)
        return start.strftime("%Y-%m-%d")

    @classmethod
    def _get_week_end(cls) -> str:
        """Get current week's end date (Sunday)."""
        today = datetime.now(timezone.utc)
        start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        days_since_monday = start.weekday()
        start_of_week = start - timedelta(days=days_since_monday)
        end_of_week = start_of_week + timedelta(days=6)
        end = end_of_week.replace(hour=23, minute=59, second=59)
        return end.strftime("%Y-%m-%d")

    @classmethod
    def _build_response(cls, response, input_tokens, output_tokens, total_tokens, execution_time) -> NutritionServiceResponse:
        """Build standardized response object."""
        total_cost = calculate_cost(input_tokens, output_tokens)

        metadata = ServiceMetadata(
            input_token_count=input_tokens,
            output_token_count=output_tokens,
            total_token_count=total_tokens,
            estimated_cost=total_cost,
            execution_time_seconds=round(execution_time, 4),
        )

        return NutritionServiceResponse(
            response=response,
            status=200,
            message="SUCCESS",
            metadata=metadata,
        )