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
    def generate_from_text(self, prompt: str) -> Tuple[NutritionResponseModel, int, int, int]:
        """Text-only generation. Returns (result, input_tokens, output_tokens, total_tokens)."""
        pass

    @abstractmethod
    def generate_from_image(self, prompt: str, image_bytes: bytes, image_mime_type: str = "image/jpeg") -> Tuple[NutritionResponseModel, int, int, int]:
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

    def generate_from_text(self, prompt: str) -> Tuple[NutritionResponseModel, int, int, int]:
        """Text-only generation via Gemini."""
        config = {
            "response_mime_type": "application/json",
            "response_schema": NutritionResponseModel,
            "temperature": 0,
        }

        response = self._generate_content(contents=prompt, config=config)

        input_tokens = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        output_tokens = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
        total_tokens = response.usage_metadata.total_token_count if response.usage_metadata else 0

        result = response.parsed

        return result, input_tokens, output_tokens, total_tokens

    def generate_from_image(self, prompt: str, image_bytes: bytes, image_mime_type: str = "image/jpeg") -> Tuple[NutritionResponseModel, int, int, int]:
        """Image + text generation via Gemini."""
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=image_mime_type)

        config = {
            "response_mime_type": "application/json",
            "response_schema": NutritionResponseModel,
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

    def _call_api(self, messages: list, with_structured_output: bool = True) -> dict:
        """Make the API call and handle errors."""
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": self._response_schema if with_structured_output else None
        }

        response = requests.post(self.url, headers=headers, json=payload, timeout=60)
        data = response.json()

        if "error" in data:
            raise Exception(f"OpenRouter error: {data['error'].get('message', 'Unknown')}")

        return data

    def generate_from_text(self, prompt: str) -> Tuple[NutritionResponseModel, int, int, int]:
        """Text-only generation via OpenRouter."""
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        data = self._call_api(messages)

        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        content = data["choices"][0]["message"]["content"]
        result = NutritionResponseModel.model_validate_json(content)

        return result, input_tokens, output_tokens, total_tokens

    def generate_from_image(self, prompt: str, image_bytes: bytes, image_mime_type: str = "image/jpeg") -> Tuple[NutritionResponseModel, int, int, int]:
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
        data = self._call_api(messages)

        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        content = data["choices"][0]["message"]["content"]
        result = NutritionResponseModel.model_validate_json(content)

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
    def get_nutrition_data(cls, query: NutritionInputPayload, provider_type: LLMProviderType = LLMProviderType.GEMINI) -> NutritionServiceResponse:
        """Analyze food from image (URL or base64) + optional text description."""
        import base64

        provider = cls._get_provider(provider_type)

        prompt = PromptService.get_nutrition_analysis_prompt_for_image(
            user_message=query.food_description or "",
            selectedGoal=query.selectedGoals,
            selectedDiet=query.dietaryPreferences,
            selectedAllergy=query.allergies,
            imageUrl=query.imageUrl,
        )

        start_time = time.time()
        image_bytes = None

        if query.imageData:
            image_bytes = base64.b64decode(query.imageData)
        elif query.imageUrl:
            image_bytes = requests.get(query.imageUrl).content

        if image_bytes:
            result, input_tokens, output_tokens, total_tokens = provider.generate_from_image(prompt, image_bytes)
        else:
            result, input_tokens, output_tokens, total_tokens = provider.generate_from_text(prompt)

        return cls._build_response(result, input_tokens, output_tokens, total_tokens, time.time() - start_time)

    @classmethod
    def log_food_nutrition_data_using_description(cls, payload: NutritionInputPayload, provider_type: LLMProviderType = LLMProviderType.GEMINI) -> NutritionServiceResponse:
        """Analyze food from text description only."""
        provider = cls._get_provider(provider_type)

        prompt = PromptService.get_nutrition_analysis_prompt_from_description(
            user_message=payload.food_description,
            selectedGoal=payload.selectedGoals,
            selectedDiet=payload.dietaryPreferences,
            selectedAllergy=payload.allergies,
        )

        start_time = time.time()
        result, input_tokens, output_tokens, total_tokens = provider.generate_from_text(prompt)

        return cls._build_response(result, input_tokens, output_tokens, total_tokens, time.time() - start_time)

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