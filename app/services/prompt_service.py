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
def get_nutrition_analysis_prompt_from_description(
    user_message: str = None,
    selectedGoal: list = None,
    selectedDiet: list = None,
    selectedAllergy: list = None,
):
    """Generate the complete nutrition analysis prompt from a description."""
    dietary_context = PromptService.get_dietary_context(
        selectedGoal, selectedDiet, selectedAllergy
    )
    user_message_instruction = PromptService.get_user_message_instruction(user_message)

    return f"""
NUTRITION ANALYSIS TASK"""
