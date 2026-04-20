import base64
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Tuple, Any

import requests

from app.exceptions import (
    ExternalServiceException,
    gemini_api_error,
    api_key_invalid,
)
from app.models.nutrition_output_payload import NutritionResponseModel
from app.services.prompt_service import PromptService
from app.models.nutrition_input_payload import NutritionInputPayload
from app.models.service_response import NutritionServiceResponse, ServiceMetadata
from app.utils.token import calculate_cost
from google import genai
from google.genai import types


class LLMProviderType(Enum):
    """Enum for LLM provider types."""
    GEMINI = "gemini"
    OPENROUTER = "openrouter"


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate_from_text(self, prompt: str, response_schema: type = NutritionResponseModel) -> Tuple[Any, int, int, int]:
        """Text-only generation. Returns (result, input_tokens, output_tokens, total_tokens)."""
        pass

    @abstractmethod
    def generate_from_image(self, prompt: str, image_bytes: bytes, response_schema: type = NutritionResponseModel, image_mime_type: str = "image/jpeg") -> Tuple[Any, int, int, int]:
        """Image + text generation. Returns (result, input_tokens, output_tokens, total_tokens)."""
        pass


class GeminiProvider(LLMProvider):
    """Gemini API implementation with structured output support."""

    def __init__(self):
        import os

        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not set")
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.client = genai.Client(api_key=self.api_key)

    def _generate_content(self, contents, config: dict) -> Any:
        """Make API call with proper error handling."""
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            return response
        except Exception as e:
            error_message = str(e).lower()

            if "rate limit" in error_message or "quota" in error_message:
                raise ExternalServiceException(
                    message="API rate limit exceeded. Please try again later.",
                    service_name="Gemini AI",
                    retry_after=60,
                ) from e
            elif "authentication" in error_message or "api key" in error_message:
                raise api_key_invalid("Google Gemini AI")
            elif "timeout" in error_message:
                raise ExternalServiceException(
                    message="Request to Gemini AI timed out. Please try again.",
                    service_name="Gemini AI",
                ) from e
            else:
                raise gemini_api_error(
                    message=f"Gemini AI service error: {str(e)}"
                ) from e

    def generate_from_text(self, prompt: str, response_schema: type = NutritionResponseModel) -> Tuple[Any, int, int, int]:
        """Text-only generation via Gemini."""
        config = {
            "response_mime_type": "application/json",
            "response_schema": response_schema,
            "temperature": 0,
        }

        response = self._generate_content(contents=prompt, config=config)

        input_tokens = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        output_tokens = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
        total_tokens = response.usage_metadata.total_token_count if response.usage_metadata else 0

        result = response.parsed

        return result, input_tokens, output_tokens, total_tokens

    def generate_from_image(self, prompt: str, image_bytes: bytes, response_schema: type = NutritionResponseModel, image_mime_type: str = "image/jpeg") -> Tuple[Any, int, int, int]:
        """Image + text generation via Gemini."""
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=image_mime_type)

        config = {
            "response_mime_type": "application/json",
            "response_schema": response_schema,
            "temperature": 0,
        }

        response = self._generate_content(contents=[prompt, image_part], config=config)

        input_tokens = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        output_tokens = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
        total_tokens = response.usage_metadata.total_token_count if response.usage_metadata else 0

        result = response.parsed

        return result, input_tokens, output_tokens, total_tokens


class OpenRouterProvider(LLMProvider):
    """OpenRouter API implementation."""

    def __init__(self):
        import os
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set")

        self.url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4")
        self._response_schema = self._build_response_schema()

    def _build_response_schema(self) -> dict:
        """Build JSON schema from NutritionResponseModel for structured output."""
        schema = NutritionResponseModel.model_json_schema()
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "nutrition_response",
                "schema": schema
            }
        }

    def _call_api(self, messages: list, response_format: dict = None) -> dict:
        """Make the API call and handle errors."""
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": response_format or self._response_schema
        }

        response = requests.post(self.url, headers=headers, json=payload, timeout=60)
        data = response.json()

        if "error" in data:
            raise Exception(f"OpenRouter error: {data['error'].get('message', 'Unknown')}")

        return data

    def _build_response_format(self, response_schema: type) -> dict:
        """Build JSON response format for a given schema."""
        schema = response_schema.model_json_schema()
        return {
            "type": "json_schema",
            "json_schema": {
                "name": response_schema.__name__.lower() + "_response",
                "schema": schema
            }
        }

    def generate_from_text(self, prompt: str, response_schema: type = NutritionResponseModel) -> Tuple[Any, int, int, int]:
        """Text-only generation via OpenRouter."""
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        response_format = self._build_response_format(response_schema)
        data = self._call_api(messages, response_format)

        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        content = data["choices"][0]["message"]["content"]
        result = response_schema.model_validate_json(content)

        return result, input_tokens, output_tokens, total_tokens

    def generate_from_image(self, prompt: str, image_bytes: bytes, response_schema: type = NutritionResponseModel, image_mime_type: str = "image/jpeg") -> Tuple[Any, int, int, int]:
        """Image + text generation via OpenRouter."""
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        data_url = f"data:image/jpeg;base64,{base64_image}"

        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}}
            ]
        }]
        response_format = self._build_response_format(response_schema)
        data = self._call_api(messages, response_format)

        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        content = data["choices"][0]["message"]["content"]
        result = response_schema.model_validate_json(content)

        return result, input_tokens, output_tokens, total_tokens


class NutritionServiceV2:
    """
    Simple nutrition analysis service.
    Uses Gemini by default, supports any LLMProvider.
    """

    _gemini_provider: Optional[LLMProvider] = None
    _openrouter_provider: Optional[LLMProvider] = None

    @classmethod
    def set_provider(cls, provider: LLMProvider):
        """Set a custom LLM provider."""
        cls._gemini_provider = provider

    @classmethod
    def _get_provider(cls, provider_type: LLMProviderType) -> LLMProvider:
        """Get the provider instance based on type."""
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
    def get_nutrition_data(cls, query: NutritionInputPayload, provider_type: LLMProviderType) -> NutritionServiceResponse:
        """Analyze food from image (URL or base64) + optional text description.

        Uses a two-step approach for deterministic, fact-checked results:
        1. Lightweight LLM extracts food names/quantities from image
        2. Web search fetches authoritative nutrition data
        3. Main LLM synthesizes image + search results for final nutrition data
        """
        from app.services.food_extractor_service import FoodExtractorService
        from app.services.search_service import SearchService
        from app.utils.debug_writer import DebugWriter

        start_time = time.time()
        run_dir = DebugWriter.start_run()

        step1_errors = []
        step2_errors = []
        step3_errors = []

        enriched_query = None
        search_results = []
        result = None
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0
        extraction_prompt = ""
        search_api_requests = []
        synthesis_prompt = ""

        step1_start = time.time()
        try:
            enriched_query, extraction_prompt = FoodExtractorService.extract_foods(
                query=query,
                provider_type=provider_type,
            )
        except Exception as e:
            step1_errors.append(str(e))
        step1_time = time.time() - step1_start

        DebugWriter.write_step(
            run_dir=run_dir,
            step_name="food_extraction",
            step_number=1,
            title="Step 1: Food Extraction (Lightweight LLM)",
            input_data={
                "image_url": query.imageUrl,
                "has_image_data": bool(query.imageData),
                "food_description": query.food_description,
                "provider": provider_type.value,
            },
            prompt=extraction_prompt,
            output_data={
                "main_query": enriched_query.main_query if enriched_query else None,
                "search_terms": [
                    {"term": t.term, "reason": t.reason}
                    for t in (enriched_query.search_terms if enriched_query else [])
                ],
                "context": enriched_query.context if enriched_query else None,
            } if enriched_query else None,
            notes=f"Execution time: {step1_time:.2f}s",
        )

        step2_start = time.time()
        if enriched_query and enriched_query.search_terms:
            try:
                search_queries = [term.term for term in enriched_query.search_terms]
                if enriched_query.main_query:
                    search_queries.insert(0, enriched_query.main_query)
                for search_query in search_queries[:5]:
                    search_api_requests.append({"query": search_query, "num_results": 1})
                    search_result = SearchService.search_web(search_query, num_results=1)
                    if search_result.results:
                        search_results.extend(search_result.results)
            except Exception as e:
                step2_errors.append(str(e))
        step2_time = time.time() - step2_start

        DebugWriter.write_step(
            run_dir=run_dir,
            step_name="web_search",
            step_number=2,
            title="Step 2: Web Search (Exa API)",
            input_data={
                "search_queries": [term.term for term in (enriched_query.search_terms if enriched_query else [])],
                "main_query": enriched_query.main_query if enriched_query else None,
            },
            api_request={"searches": search_api_requests} if search_api_requests else None,
            output_data={
                "total_results": len(search_results),
                "results": [
                    {"title": r.title, "url": r.url, "snippet": r.snippet}
                    for r in search_results[:10]
                ],
                "errors": step2_errors or None,
            },
            notes=f"Execution time: {step2_time:.2f}s",
        )

        search_context = cls._build_search_context(search_results)

        synthesis_prompt = PromptService.get_nutrition_analysis_prompt_for_image(
            user_message=query.food_description or "",
            selectedGoal=query.selectedGoals,
            selectedDiet=query.dietaryPreferences,
            selectedAllergy=query.allergies,
            imageUrl=query.imageUrl,
            web_research_context=search_context,
            enriched_query=enriched_query.main_query if enriched_query else None,
        )

        provider = cls._get_provider(provider_type)

        image_bytes = None
        if query.imageData:
            image_bytes = base64.b64decode(query.imageData)
        elif query.imageUrl:
            image_bytes = requests.get(query.imageUrl).content

        step3_start = time.time()
        try:
            if image_bytes:
                result, input_tokens, output_tokens, total_tokens = provider.generate_from_image(synthesis_prompt, image_bytes)
            else:
                result, input_tokens, output_tokens, total_tokens = provider.generate_from_text(synthesis_prompt)
        except Exception as e:
            step3_errors.append(str(e))
        step3_time = time.time() - step3_start

        DebugWriter.write_step(
            run_dir=run_dir,
            step_name="nutrition_synthesis",
            step_number=3,
            title="Step 3: Nutrition Synthesis (Main LLM)",
            input_data={
                "has_image": bool(image_bytes),
                "image_size_bytes": len(image_bytes) if image_bytes else 0,
                "search_context_length": len(search_context),
                "enriched_query": enriched_query.main_query if enriched_query else None,
            },
            prompt=synthesis_prompt,
            output_data=result,
            notes=f"Execution time: {step3_time:.2f}s, Tokens: {total_tokens}",
        )

        execution_time = time.time() - start_time

        DebugWriter.write_summary(
            run_dir=run_dir,
            total_steps=3,
            execution_time=execution_time,
            final_result=result,
            errors=step1_errors + step2_errors + step3_errors if (step1_errors or step2_errors or step3_errors) else None,
        )

        return cls._build_response(result, input_tokens, output_tokens, total_tokens, execution_time)

    @classmethod
    def _build_search_context(cls, search_results: list) -> str:
        """Build context string from search results for LLM consumption."""
        if not search_results:
            return ""

        context_parts = []
        for i, result in enumerate(search_results[:5], 1):
            title = getattr(result, "title", "") or ""
            url = getattr(result, "url", "") or ""
            snippet = getattr(result, "snippet", "") or ""

            if snippet and len(snippet) > 50:
                context_parts.append(f"[Source {i}] {title} ({url})")
                context_parts.append(f"Content: {snippet[:500]}")
            elif title:
                context_parts.append(f"[Source {i}] {title} ({url})")

        return "\n".join(context_parts) if context_parts else ""

    @classmethod
    def log_food_nutrition_data_using_description(cls, payload: NutritionInputPayload, provider_type: LLMProviderType) -> NutritionServiceResponse:
        """Analyze food from text description only with enrichment."""
        from app.services.food_extractor_service import FoodExtractorService
        from app.utils.debug_writer import DebugWriter

        start_time = time.time()
        run_dir = DebugWriter.start_run()

        step1_errors = []
        step2_errors = []
        step3_errors = []

        enriched_query = None
        search_results = []
        extraction_prompt = ""
        synthesis_prompt = ""
        result = None
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0

        step1_start = time.time()
        try:
            enriched_query, extraction_prompt = FoodExtractorService.extract_foods_from_text(
                food_description=payload.food_description,
                provider_type=provider_type,
            )
        except Exception as e:
            step1_errors.append(str(e))
        step1_time = time.time() - step1_start

        DebugWriter.write_step(
            run_dir=run_dir,
            step_name="food_extraction",
            step_number=1,
            title="Step 1: Food Extraction from Text (Lightweight LLM)",
            input_data={
                "food_description": payload.food_description,
                "provider": provider_type.value,
            },
            prompt=extraction_prompt,
            output_data={
                "main_query": enriched_query.main_query if enriched_query else None,
                "search_terms": [
                    {"term": t.term, "reason": t.reason}
                    for t in (enriched_query.search_terms if enriched_query else [])
                ],
                "context": enriched_query.context if enriched_query else None,
            } if enriched_query else None,
            notes=f"Execution time: {step1_time:.2f}s",
        )

        step2_start = time.time()
        search_api_requests = []
        from app.services.search_service import SearchService
        if enriched_query and enriched_query.search_terms:
            try:
                search_queries = [term.term for term in enriched_query.search_terms]
                if enriched_query.main_query:
                    search_queries.insert(0, enriched_query.main_query)

                for search_query in search_queries[:5]:
                    search_api_requests.append({"query": search_query, "num_results": 1})
                    search_result = SearchService.search_web(search_query, num_results=1)
                    if search_result.results:
                        search_results.extend(search_result.results)
            except Exception as e:
                step2_errors.append(str(e))
        step2_time = time.time() - step2_start

        DebugWriter.write_step(
            run_dir=run_dir,
            step_name="web_search",
            step_number=2,
            title="Step 2: Web Search (Exa API)",
            input_data={
                "search_queries": [term.term for term in (enriched_query.search_terms if enriched_query else [])],
                "main_query": enriched_query.main_query if enriched_query else None,
            },
            api_request={"searches": search_api_requests} if search_api_requests else None,
            output_data={
                "total_results": len(search_results),
                "results": [
                    {"title": r.title, "url": r.url, "snippet": r.snippet}
                    for r in search_results[:5]
                ],
                "errors": step2_errors or None,
            },
            notes=f"Execution time: {step2_time:.2f}s",
        )

        search_context = cls._build_search_context(search_results)

        synthesis_prompt = PromptService.get_nutrition_analysis_prompt_for_image(
            user_message=payload.food_description or "",
            selectedGoal=payload.selectedGoals,
            selectedDiet=payload.dietaryPreferences,
            selectedAllergy=payload.allergies,
            imageUrl=payload.imageUrl,
            web_research_context=search_context,
            enriched_query=enriched_query.main_query if enriched_query else None,
        )

        provider = cls._get_provider(provider_type)

        image_bytes = None
        if payload.imageData:
            image_bytes = base64.b64decode(payload.imageData)
        elif payload.imageUrl:
            image_bytes = requests.get(payload.imageUrl).content

        step3_start = time.time()
        try:
            if image_bytes:
                result, input_tokens, output_tokens, total_tokens = provider.generate_from_image(synthesis_prompt, image_bytes)
            else:
                result, input_tokens, output_tokens, total_tokens = provider.generate_from_text(synthesis_prompt)
        except Exception as e:
            step3_errors.append(str(e))
        step3_time = time.time() - step3_start

        DebugWriter.write_step(
            run_dir=run_dir,
            step_name="nutrition_synthesis",
            step_number=3,
            title="Step 3: Nutrition Synthesis (Main LLM)",
            input_data={
                "has_image": bool(image_bytes),
                "image_size_bytes": len(image_bytes) if image_bytes else 0,
                "search_context_length": len(search_context),
                "enriched_query": enriched_query.main_query if enriched_query else None,
            },
            prompt=synthesis_prompt,
            output_data=result,
            notes=f"Execution time: {step3_time:.2f}s, Tokens: {total_tokens}",
        )

        execution_time = time.time() - start_time

        DebugWriter.write_summary(
            run_dir=run_dir,
            total_steps=3,
            execution_time=execution_time,
            final_result=result,
            errors=step1_errors + step2_errors + step3_errors if (step1_errors or step2_errors or step3_errors) else None,
        )

        return cls._build_response(result, input_tokens, output_tokens, total_tokens, execution_time)

    @classmethod
    def _build_response(cls, result, input_tokens, output_tokens, total_tokens, execution_time) -> NutritionServiceResponse:
        """Build the standardized response object."""
        total_cost = calculate_cost(input_tokens, output_tokens)

        metadata = ServiceMetadata(
            input_token_count=input_tokens,
            output_token_count=output_tokens,
            total_token_count=total_tokens,
            estimated_cost=total_cost,
            execution_time_seconds=round(execution_time, 4),
        )

        return NutritionServiceResponse(
            response=result,
            status=200,
            message="SUCCESS",
            metadata=metadata,
        )
