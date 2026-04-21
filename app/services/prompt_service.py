import base64


class PromptService:
    """
    Service class for handling prompt generation for nutrition analysis.
    """

    @staticmethod
    def get_dietary_context(
        selectedGoal: list = None,
        selectedDiet: list = None,
        selectedAllergy: list = None,
    ) -> str:
        """Generate dietary context string based on user preferences."""
        dietary_context = ""
        if selectedDiet:
            dietary_context += f"The user follows these dietary preferences: {', '.join(selectedDiet)}. "
        if selectedAllergy:
            dietary_context += (
                f"The user has allergies to: {', '.join(selectedAllergy)}. "
            )
        if selectedGoal:
            dietary_context += (
                f"The user has the following health goals: {', '.join(selectedGoal)}. "
            )
        return dietary_context

    @staticmethod
    def get_user_message_instruction(user_message: str = None) -> str:
        """Generate user message instruction for the prompt."""
        return (
            f"The user states: '{user_message}'. Only consider what is visible in the image and what the user explicitly mentions. "
            "Do not assume any additional ingredients like sausages unless clearly visible. "
            if user_message
            else "Only include ingredients that are clearly visible in the image. Do not guess hidden components such as meats or sauces unless clearly identifiable."
        )

    @staticmethod
    def get_nutrition_analysis_prompt_for_image(
        user_message: str = None,
        selectedGoal: list = None,
        selectedDiet: list = None,
        selectedAllergy: list = None,
        imageUrl: str = None,
        web_research_context: str = None,
        enriched_query: str = None,
    ) -> str:
        """Generate the complete nutrition analysis prompt."""
        dietary_context = PromptService.get_dietary_context(
            selectedGoal, selectedDiet, selectedAllergy
        )

        web_context_section = ""
        if web_research_context:
            web_context_section = f"""
NUTRITION DATA FROM WEB SEARCH:
{web_research_context}

IMPORTANT: Extract actual nutrition values (calories, protein, carbs, fat, fiber, sodium, sugar) from the search results above.
- Prioritize values from USDA, FDA, or official manufacturer sources.
- Ignore app promotional content, FAQ pages, and non-nutrition pages.
- If search results are empty or unhelpful, use your knowledge of typical nutrition values for this food type.
- Calculate totals for the actual quantity mentioned.
"""

        enriched_query_section = ""
        if enriched_query:
            enriched_query_section = f"""
IDENTIFIED FOOD: "{enriched_query}"
"""

        return f"""
You are a nutrition expert. Analyze the food and provide accurate nutrition information.

{ dietary_context}

{enriched_query_section}

{web_context_section}

RULES:
1. Use EXACT quantities mentioned by the user
2. Calculate TOTAL nutrition for the quantity described (not per serving)
3. Consider user's dietary preferences and allergies in your analysis
4. confidenceScore: How confident you are in the data (10=very confident, based on authoritative sources)
5. Return ONLY valid JSON

JSON format:
{{
  "status": "SUCCESS" or "ERROR",
  "message": "brief note",
  "foodName": "exact food name from user",
  "portion": "gram" or "piece" or "slices" or "cup",
  "portionSize": number,
  "imageUrl": "{imageUrl if imageUrl else ""}",
  "ingredients": [
    {{
      "name": "ingredient name",
      "calories": integer,
      "protein": integer,
      "carbs": integer,
      "fiber": integer,
      "fat": integer,
      "sugar": integer (optional),
      "sodium": integer (optional),
      "healthScore": integer 0-10,
      "healthComments": "brief comment"
    }}
  ],
  "primaryConcerns": [{{"issue": "concern name", "explanation": "why", "recommendations": [{{"food": "food name", "quantity": "amount", "reasoning": "why helpful"}}]}}],
  "suggestAlternatives": [{{"name": "alt food", "calories": integer, "protein": integer, "carbs": integer, "fiber": integer, "fat": integer, "healthScore": integer, "healthComments": "comment"}}],
  "overallHealthScore": integer 0-10,
  "overallHealthComments": "overall assessment"
}}

User described: "{user_message}"
Only analyze what the user explicitly mentions. If no food, return status "ERROR".
"""

    @staticmethod
    def get_nutrition_analysis_prompt_from_description(
        user_message: str = None,
        selectedGoal: list = None,
        selectedDiet: list = None,
        selectedAllergy: list = None,
        web_research_context: str = None,
    ) -> str:
        """Generate the complete nutrition analysis prompt from a description."""
        dietary_context = PromptService.get_dietary_context(
            selectedGoal, selectedDiet, selectedAllergy
        )
        user_message_instruction = PromptService.get_user_message_instruction(
            user_message
        )

        web_context_section = ""
        if web_research_context:
            web_context_section = f"""
WEB RESEARCH CONTEXT:
{web_research_context}

Use the above web research to verify and enhance nutritional data accuracy. Cross-reference with official sources where possible.
"""

        return f"""
NUTRITION ANALYSIS TASK:
You are a nutrition expert. Analyze the food description and return ONLY valid JSON.

USER INPUT: "{user_message}"
DIETARY CONTEXT: {dietary_context}

If it's not a  food  return:
{{
  "message": "No food detected in image",
  "foodName": "Error: No food detected",
  "portion": "cup",
  "portionSize": 0,
  "ingredients": [],
  "primaryConcerns": [],
  "suggestAlternatives": [],
  "overallHealthScore": 0,
  "overallHealthComments": "No food detected in image"
}}

INSTRUCTIONS:
1. Extract EXACT quantity from description (e.g., "2 Oreo cookies" = analyze 2 cookies total)
2. Use official nutrition data (USDA/manufacturer labels)
3. Calculate TOTAL nutrition for the exact quantity mentioned
4. Keep all comments under word limits
5. Use integers for all numeric values (no decimals)
6. Use third person ("This food is..." not "You...")
7. overall health score from 0-10, with 10 being healthiest
8. Provide evidence-based recommendations
9. overallComments: MAX 40 words , explain if the food is healthy or not and why 
10. confidenceScore: Score from 0-10 indicating confidence in analysis
11. Suggest 3 alternative foods with better nutritional properties




CRITICAL ANALYSIS REQUIREMENTS:
1. EXACT QUANTITY MATCHING: Parse the EXACT quantity mentioned in the user's description. If they say "2 Oreo cookies", analyze specifically for 2 cookies, not 1 or a generic serving.

2. PRECISE NUTRITIONAL LOOKUP: Use authoritative nutrition data:
   - USDA FoodData Central as primary source
   - Official manufacturer nutrition labels (Nabisco for Oreos, etc.)
   - Peer-reviewed nutritional databases
   - Cross-reference multiple sources for accuracy

3. MATHEMATICAL PRECISION: 
   - Calculate totals by multiplying per-unit values by exact quantity
   - Example: If 1 Oreo = 53 calories, then 2 Oreos = 106 calories
   - Round to nearest whole number for calories, maintain precision for macros

4. BRAND-SPECIFIC DATA: When brand names are mentioned (Oreo, Lay's, etc.), use that specific brand's nutritional profile, not generic equivalents.

5. VERIFICATION CROSS-CHECK: Before finalizing values, verify that:
   - Total calories match sum of macros (protein×4 + carbs×4 + fat×9)
   - Values are realistic for the food type and quantity
   - Portion size reflects the actual amount described



QUALITY ASSURANCE CHECKLIST:
✓ Calories match the exact quantity described
✓ Macro totals are mathematically consistent  
✓ Brand-specific data used when applicable
✓ Portion size reflects actual amount consumed
✓ Health scores are evidence-based
✓ Recommendations are specific and actionable

CRITICAL RULES:
        - Return ONLY valid JSON, no extra text
        - All numbers must be integers (no decimals)
        - Comments must be under word limits
        - Use third person ("This food is..." not "You...")
        - Calculate for EXACT quantity mentioned
        """

    @staticmethod
    def get_single_day_diet_prompt(
        diet_input,
        day_name: str,
        day_index: int,
        daily_targets: dict,
        used_foods: list = None,
    ) -> str:
        """Generate a prompt for creating a single day's meal plan.

        Args:
            diet_input: DietInput with user preferences
            day_name: Name of the day (Monday, etc.)
            day_index: Day index (0-6)
            daily_targets: Target macros for this specific day
            used_foods: List of foods already used in previous days
        """
        dietary_context = PromptService.get_dietary_context(
            selectedGoal=diet_input.selectedGoals,
            selectedDiet=diet_input.dietaryPreferences,
            selectedAllergy=diet_input.allergies,
        )

        disliked = ", ".join(diet_input.dislikedFoods) if diet_input.dislikedFoods else "none"
        diseases = ", ".join(diet_input.anyDiseases) if diet_input.anyDiseases else "none"

        variety_section = ""
        if used_foods and len(used_foods) > 0:
            variety_section = f"""
VARIETY REQUIREMENT - IMPORTANT:
You MUST use different ingredients than previous days. Here are foods already used (DO NOT REPEAT unless unavoidable):
{', '.join(used_foods[:30])}

Rules for variety:
- If you used spinach on a previous day, use kale, mustard greens, methi, or cabbage today
- If you used oats for breakfast before, use quinoa, buckwheat, ragi, or besan chilla today
- If you used the same fish twice this week, choose a different fish today
- Vary your vegetables: use different sabzi types each day
- Rotate protein sources: eggs one day, fish another, chicken another, lentils/paneer another
- Change grain bases: rice one day, quinoa another, buckwheat another
"""

        return f"""
You are a certified dietitian creating a single day's meal plan.

USER PROFILE:
- Calorie Target: {daily_targets['calories']} kcal (±50 allowed)
- Protein Target: {daily_targets['protein']}g (±5g allowed)
- Carbs Target: {daily_targets['carbs']}g (±10g allowed)
- Fat Target: {daily_targets['fat']}g (±5g allowed)
- Fiber Target: {daily_targets['fiber']}g (minimum)

{variety_section}

DIETARY CONTEXT:
{dietary_context}

RESTRICTIONS:
- DISLIKED FOODS to exclude: {disliked}
- HEALTH CONDITIONS to consider: {diseases}
- USER INSTRUCTIONS: {diet_input.prompt}

MEAL REQUIREMENTS FOR {day_name.upper()} (Day {day_index}):

1. BREAKFAST (25-30% of daily calories)
   - Must include protein + complex carbs + fiber
   - Think: eggs, oats, yogurt, smoothies with protein

2. LUNCH (35-40% of daily calories)
   - Must include lean protein + carbs + vegetables
   - Think: fish/chicken with rice and sabzi

3. DINNER (25-30% of daily calories)
   - Must include protein + vegetables (low carb preference)
   - Think: grilled protein with stir-fried greens

4. SNACKS (10-15% of daily calories)
   - 1-2 healthy snacks for satiety
   - Think: nuts, fruits, yogurt, boiled eggs

5. CHEAT MEAL (optional, ~200-400 calories)
   - One small indulgence the user will enjoy
   - Should be something they genuinely crave (e.g.,  sweets, biryani)
   - NOT just "dark chocolate" - make it satisfying

MACRO BALANCE RULES (STRICT):
- Protein at every meal (minimum 20g per main meal)
- Carbs from whole grains, fruits, vegetables
- Healthy fats from fish, nuts, avocados, olive oil
- Fiber minimum 25g per day
- Distribute protein evenly: ~30g breakfast, ~40g lunch, ~35g dinner

THYROID-SUPPORTIVE FOODS (include 2-3x per week):
- Fish ( Rohu, Hilsa, Bhetki, Tilapia)
- Eggs
- Spinach, broccoli
- Pumpkin seeds
- Selenium-rich foods

GENERATE THE DAY'S MEALS following this EXACT JSON format:
{{
  "dayIndex": {day_index},
  "dayName": "{day_name}",
  "meals": {{
    "breakfast": {{
      "foodName": "complete dish name (e.g., 'Rohu Machher Jhol with Brown Rice')",
      "portion": "any common portion unit (e.g., cup, gram, slices, pieces, serving, bowl, plate, whole)",
      "portionSize": number,
      "confidenceScore": 8-10,
      "ingredients": [
        {{"name": "ingredient", "calories": int, "protein": int, "carbs": int, "fiber": int, "fat": int, "healthScore": int, "healthComments": "brief"}}
      ],
      "primaryConcerns": [],
      "suggestAlternatives": [],
      "overallHealthScore": 7-10,
      "overallHealthComments": "why this meal works"
    }},
    "lunch": {{
      "foodName": "complete dish name",
      "portion": "any common portion unit (e.g., cup, gram, slices, pieces, serving, bowl, plate, whole)",
      "portionSize": number,
      "confidenceScore": 8-10,
      "ingredients": [
        {{"name": "ingredient", "calories": int, "protein": int, "carbs": int, "fiber": int, "fat": int, "healthScore": int, "healthComments": "brief"}}
      ],
      "primaryConcerns": [],
      "suggestAlternatives": [],
      "overallHealthScore": 7-10,
      "overallHealthComments": "why this meal works"
    }},
    "dinner": {{
      "foodName": "complete dish name",
      "portion": "any common portion unit (e.g., cup, gram, slices, pieces, serving, bowl, plate, whole)",
      "portionSize": number,
      "confidenceScore": 8-10,
      "ingredients": [
        {{"name": "ingredient", "calories": int, "protein": int, "carbs": int, "fiber": int, "fat": int, "healthScore": int, "healthComments": "brief"}}
      ],
      "primaryConcerns": [],
      "suggestAlternatives": [],
      "overallHealthScore": 7-10,
      "overallHealthComments": "why this meal works"
    }},
    "snacks": [
      {{
        "foodName": "complete dish name (e.g., 'Boiled Eggs with Salt')",
        "portion": "any common portion unit (e.g., cup, gram, slices, pieces, serving, bowl, plate, whole)",
        "portionSize": number,
        "confidenceScore": 8-10,
        "ingredients": [
          {{"name": "ingredient", "calories": int, "protein": int, "carbs": int, "fiber": int, "fat": int, "healthScore": int, "healthComments": "brief"}}
        ],
        "primaryConcerns": [],
        "suggestAlternatives": [],
        "overallHealthScore": 7-10,
        "overallHealthComments": "why this snack works"
      }}
    ]
  }},
  "cheatMealOfTheDay": {{
    "foodName": "complete dish name (e.g., ' Mishti Doi')",
    "portion": "any common portion unit (e.g., cup, gram, slices, pieces, serving, bowl, plate, whole)",
    "portionSize": number,
    "confidenceScore": 8-10,
    "ingredients": [
      {{"name": "ingredient", "calories": int, "protein": int, "carbs": int, "fiber": int, "fat": int, "healthScore": int, "healthComments": "brief"}}
    ],
    "primaryConcerns": [],
    "suggestAlternatives": [],
    "overallHealthScore": 7-10,
    "overallHealthComments": "why this treat works"
  }},
  "totalNutrition": {{
    "calories": total,
    "protein": total,
    "carbs": total,
    "fiber": total,
    "fat": total
  }}
}}

CRITICAL RULES:
1. Calculate ACTUAL totals from ingredients, not estimates
2. Ensure totals match sum of all meals + snacks
3. Protein must exceed {daily_targets['protein'] - 5}g (don't under-sell protein)
4. Fiber must be at least {daily_targets['fiber']}g
5. Every main meal must have a protein source
6. Return ONLY valid JSON, no extra text
7. All numeric values must be INTEGERS (no decimals/floats - round to nearest whole number)
8. Use REAL food items with accurate nutrition data based on user's cuisine preferences
9. DISH NAMES MUST BE COMPLETE /INDIAN DISHES with actual preparation style:
   - GOOD: "Aloo Paratha with Curd and Pickle", "Eggs Keema with Roti", "Moong Dal Cheela with Green Chutney"
   - BAD: "Eggs", "Paratha", "Dal", "Oats", "Besan"
   - For FISH: always say "Machher Jhol" or "Machher Paturi" or "Fish Curry" not just "Rohu Fish"
   - For BREADS: always say "Roti with Ghee" or "Paratha" not just "Roti"
   - For DAL: always say "Dal Fry with Rice" or "Dal Tadka" not just "Dal"
   - foodName must be a complete  dish name that describes the WHOLE dish, not just the main ingredient
10. INGREDIENT NAMES should also be specific dishes/preparations, not raw ingredients:
    - BAD: "Rolled Oats", "Greek Yogurt", "Besan"
    - GOOD: "Oats Porridge with Milk", "Greek Yogurt with Honey", "Besan Chilla"
    - Every ingredient name should be something you'd actually eat, not a raw pantry item
11. STRICT VARIETY - No ingredient should appear more than twice per week:
    - Check the used_foods list and choose DIFFERENT proteins, vegetables, grains
    - If chicken appeared Monday, use fish or paneer Wednesday
    - If palak appeared Tuesday, use methi or lauki Wednesday
    - If brown rice appeared, use quinoa or buckwheat Thursday"""

    @staticmethod
    def get_suggest_alternate_prompt(request) -> str:
        """Generate prompt for suggesting alternate meals."""
        dietary_context = PromptService.get_dietary_context(
            selectedGoal=request.selectedGoals,
            selectedDiet=request.dietaryPreferences,
            selectedAllergy=request.allergies,
        )

        disliked = ", ".join(request.dislikedFoods) if request.dislikedFoods else "none"
        diseases = ", ".join(request.anyDiseases) if request.anyDiseases else "none"

        return f"""
You are a nutrition expert. Suggest 5 healthy alternatives to the current meal.

CURRENT MEAL: {request.currentMeal.foodName}
Meal Type: {request.mealType}

USER'S PREFERENCE: {request.prompt}

DIETARY CONTEXT:
{dietary_context}

RESTRICTIONS:
- Disliked foods to avoid: {disliked}
- Health conditions: {diseases}

Generate EXACTLY 5 alternative meals that:
1. All fit the same meal type ({request.mealType})
2. Are nutritionally similar or better
3. Respect dietary preferences and allergies
4. Align with the user's preference: "{request.prompt}"
5. Are diverse from each other (different proteins, vegetables, preparation styles)
6. Are real food items with accurate nutrition data

DISH NAME RULES:
- Must be COMPLETE /Indian dish names with preparation style
- GOOD: "Bhuna Khichuri with Egg Curry", "Paneer Tikka with Mint Chutney", "Hilsa Machher Jhol with Rice"
- BAD: "Rice", "Fish", "Paneer" (just raw ingredients)

Return ONLY valid JSON with exactly 5 alternatives:
{{
  "alternatives": [
    {{
      "foodName": "alternative 1 dish name",
      "portion": "any common portion unit",
      "portionSize": number,
      "ingredients": [{{"name": "ingredient", "calories": int, "protein": int, "carbs": int, "fiber": int, "fat": int, "healthScore": int, "healthComments": "brief"}}],
      "primaryConcerns": [],
      "suggestAlternatives": [],
      "overallHealthScore": int 0-10,
      "overallHealthComments": "brief assessment",
      "confidenceScore": int 0-10
    }},
    ...4 more alternatives...
  ]
}}

CRITICAL RULES:
1. Return ONLY valid JSON with exactly 5 alternatives
2. All numeric values must be integers
3. overallHealthComments max 40 words per meal
4. Make alternatives diverse (different main ingredients, different cooking styles)
5. confidenceScore reflects data accuracy (use real nutrition data)
"""
