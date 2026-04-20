import base64
import time
from typing import Optional, Tuple

import requests

from app.agent.models import EnrichedQuery, SearchTerm
from app.models.nutrition_input_payload import NutritionInputPayload
from app.services.nutrition_service_v2 import LLMProviderType
from app.services.search_service import SearchService


class FoodExtractorService:
    """
    Lightweight service to extract food names and quantities from images or text.
    Uses vision-capable LLM to identify food items, then enriches with search terms.
    """

    _gemini_provider = None
    _openrouter_provider = None

    @classmethod
    def _get_provider(cls, provider_type: LLMProviderType):
        from app.services.nutrition_service_v2 import GeminiProvider, OpenRouterProvider

        if provider_type == LLMProviderType.GEMINI:
            if cls._gemini_provider is None:
                cls._gemini_provider = GeminiProvider()
            return cls._gemini_provider
        elif provider_type == LLMProviderType.OPENROUTER:
            if cls._openrouter_provider is None:
                cls._openrouter_provider = OpenRouterProvider()
            return cls._openrouter_provider
        raise ValueError(f"Unknown provider type: {provider_type}")

    @classmethod
    def get_food_extraction_prompt(cls) -> str:
        return """You are a food identification expert. Analyze the provided image and extract all visible food items with their quantities.

TASK:
1. Identify each distinct food item visible in the image
2. Estimate quantities/serving sizes for each item
3. Note any visible brand names, packaging, or labels
4. Food name should be specific (e.g., "Nabisco Oreo chocolate sandwich cookie" instead of just "cookie")
5. We want to fetch the nutrition facts for these items, so be as specific as possible in naming and quantifying them.
6. The search terms should be focused on finding accurate nutrition information from reliable sources like USDA, manufacturer labels, or FDA databases.

OUTPUT FORMAT:
Return ONLY valid JSON with this exact structure:
{
  "main_query": "Single, clear food query string suitable for web search",
  "search_terms": [
    {
      "term": "Specific nutrition search term",
      "reason": "Why this specific term is needed for accurate nutrition analysis"
    }
  ],
  "context": "Brief description of the meal context, visible brands, and any other relevant details"
}

CRITICAL RULES:
- For each food item, provide at least 2-3 focused search terms for nutrition lookup
- Include brand-specific searches when visible
- Include USDA or official nutrition database references in search terms when possible
- Quantities should be specific (e.g., "2 cookies", "1 cup", "150g")
- If no food is visible, return empty main_query and search_terms
"""

    @classmethod
    def get_food_extraction_from_text_prompt(cls, food_description: str) -> str:
        return f"""You are a food identification expert. Analyze the provided food description and extract all food items mentioned.

TASK:
1. Identify each distinct food item mentioned in the description
2. Note exact quantities/serving sizes mentioned
3. Note any brand names mentioned
4. Infer reasonable quantities if implied (e.g., "a bowl of rice" = approximately 1 cup or 200g)

FOOD DESCRIPTION: "{food_description}"

OUTPUT FORMAT:
Return ONLY valid JSON with this exact structure:
{{
  "main_query": "Single, clear food query string suitable for web search",
  "search_terms": [
    {{
      "term": "Specific nutrition search term",
      "reason": "Why this specific term is needed for accurate nutrition analysis"
    }}
  ],
  "context": "Brief description of the meal context"
}}

CRITICAL RULES:
- Use the EXACT quantities mentioned in the description
- If no specific quantity is mentioned, estimate a reasonable serving size
- For each food item, provide at least 2-3 focused search terms for nutrition lookup
- Include brand-specific searches when applicable
- Include USDA or official nutrition database references in search terms when possible
"""

    @classmethod
    def extract_foods(
        cls,
        query: NutritionInputPayload,
        provider_type: LLMProviderType,
    ) -> Tuple[EnrichedQuery, str]:
        """
        Extract food items from image and return enriched query for nutrition search.

        Args:
            query: NutritionInputPayload containing image data/url and user description
            provider_type: LLM provider to use (GEMINI or OPENROUTER)

        Returns:
            Tuple of (EnrichedQuery, prompt_used)
        """
        provider = cls._get_provider(provider_type)

        prompt = cls.get_food_extraction_prompt()
        user_context = ""
        if query.food_description:
            user_context = f"\nUser provided description: {query.food_description}"
        full_prompt = f"{prompt}{user_context}"

        image_bytes = None

        if query.imageData:
            image_bytes = base64.b64decode(query.imageData)
        elif query.imageUrl:
            image_bytes = requests.get(query.imageUrl).content

        result, input_tokens, output_tokens, total_tokens = provider.generate_from_image(
            full_prompt, image_bytes, EnrichedQuery
        )

        if hasattr(result, "main_query") and result.main_query:
            search_terms = []
            if hasattr(result, "search_terms") and result.search_terms:
                for term in result.search_terms:
                    if isinstance(term, dict):
                        search_terms.append(SearchTerm(term=term.get("term", ""), reason=term.get("reason", "")))
                    else:
                        search_terms.append(term)

            return EnrichedQuery(
                main_query=result.main_query,
                search_terms=search_terms,
                context=result.context if hasattr(result, "context") else "",
            ), full_prompt

        raw_result_str = getattr(result, "main_query", None)
        if raw_result_str is None:
            raw_result_str = str(result) if result else "Empty result"

        return EnrichedQuery(
            main_query="",
            search_terms=[],
            context=f"No food detected - Raw result: {raw_result_str[:200]}",
        ), full_prompt

    @classmethod
    def extract_foods_from_text(
        cls,
        food_description: str,
        provider_type: LLMProviderType,
    ) -> Tuple[EnrichedQuery, str]:
        """
        Extract food items from text description and return enriched query for nutrition search.

        Args:
            food_description: Text description of food items
            provider_type: LLM provider to use (GEMINI or OPENROUTER)

        Returns:
            Tuple of (EnrichedQuery, prompt_used)
        """
        provider = cls._get_provider(provider_type)

        prompt = cls.get_food_extraction_from_text_prompt(food_description)

        result, input_tokens, output_tokens, total_tokens = provider.generate_from_text(
            prompt, EnrichedQuery
        )

        if hasattr(result, "main_query") and result.main_query:
            search_terms = []
            if hasattr(result, "search_terms") and result.search_terms:
                for term in result.search_terms:
                    if isinstance(term, dict):
                        search_terms.append(SearchTerm(term=term.get("term", ""), reason=term.get("reason", "")))
                    else:
                        search_terms.append(term)

            return EnrichedQuery(
                main_query=result.main_query,
                search_terms=search_terms,
                context=result.context if hasattr(result, "context") else "",
            ), prompt

        raw_result_str = getattr(result, "main_query", None)
        if raw_result_str is None:
            raw_result_str = str(result) if result else "Empty result"

        return EnrichedQuery(
            main_query="",
            search_terms=[],
            context=f"No food detected - Raw result: {raw_result_str[:200]}",
        ), prompt

    @classmethod
    def extract_and_search(
        cls,
        query: NutritionInputPayload,
        provider_type: LLMProviderType,
        num_search_results: int = 1,
    ) -> Tuple[EnrichedQuery, list, str]:
        """
        Extract foods from image, perform web searches, and return enriched data.

        Args:
            query: NutritionInputPayload containing image data/url and user description
            provider_type: LLM provider to use (GEMINI or OPENROUTER)
            num_search_results: Number of search results per search term

        Returns:
            Tuple of (EnrichedQuery, list of search results, prompt_used)
        """
        enriched_query, prompt = cls.extract_foods(query, provider_type)

        search_results = []
        if enriched_query.search_terms:
            search_queries = [term.term for term in enriched_query.search_terms]
            if enriched_query.main_query:
                search_queries.insert(0, enriched_query.main_query)

            for search_query in search_queries[:5]:
                result = SearchService.search_web(search_query, num_results=num_search_results)
                if result.results:
                    search_results.extend(result.results)

        return enriched_query, search_results, prompt

    @classmethod
    def extract_foods_from_text_and_search(
        cls,
        food_description: str,
        provider_type: LLMProviderType,
        num_search_results: int = 1,
    ) -> Tuple[EnrichedQuery, list, str]:
        """
        Extract foods from text description, perform web searches, and return enriched data.

        Args:
            food_description: Text description of food items
            provider_type: LLM provider to use (GEMINI or OPENROUTER)
            num_search_results: Number of search results per search term

        Returns:
            Tuple of (EnrichedQuery, list of search results, prompt_used)
        """
        enriched_query, prompt = cls.extract_foods_from_text(food_description, provider_type)

        search_results = []
        if enriched_query.search_terms:
            search_queries = [term.term for term in enriched_query.search_terms]
            if enriched_query.main_query:
                search_queries.insert(0, enriched_query.main_query)

            for search_query in search_queries[:5]:
                result = SearchService.search_web(search_query, num_results=num_search_results)
                if result.results:
                    search_results.extend(result.results)

        return enriched_query, search_results, prompt