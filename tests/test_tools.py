import pytest
from unittest.mock import patch, MagicMock

from app.agent.tools import analyse_image, analyse_food_description


class TestAnalyseImageTool:
    """Test analyse_image with image only - no mocking of tools.py internal logic."""

    def test_analyse_image_with_url(self):
        """User provides food image URL - tool should call NutritionService and return result."""
        with patch("app.agent.tools.NutritionService") as mock_service:
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "response": {
                    "foodName": "Pizza Slice",
                    "overallHealthScore": 6,
                    "status": 200,
                },
                "status": 200,
                "message": "SUCCESS",
            }
            mock_service.get_nutrition_data.return_value = mock_response

            result = analyse_image.invoke({
                "image_url": "https://example.com/pizza.jpg",
            })

            mock_service.get_nutrition_data.assert_called_once()
            call_kwargs = mock_service.get_nutrition_data.call_args.kwargs
            assert call_kwargs["query"].imageUrl == "https://example.com/pizza.jpg"
            assert result["response"]["foodName"] == "Pizza Slice"

    def test_analyse_image_requires_image(self):
        """Tool must receive either image_url or image_data, otherwise raise ValueError."""
        with pytest.raises(ValueError, match="Either image_url or image_data must be provided"):
            analyse_image.invoke({})

    def test_analyse_image_with_user_profile(self):
        """User profile (dietary prefs, allergies, goals) should be passed to service."""
        with patch("app.agent.tools.NutritionService") as mock_service:
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "response": {"foodName": "Grilled Chicken"},
                "status": 200,
                "message": "SUCCESS",
            }
            mock_service.get_nutrition_data.return_value = mock_response

            analyse_image.invoke({
                "image_url": "https://example.com/chicken.jpg",
                "dietary_preferences": ["high-protein", "low-carb"],
                "allergies": ["gluten"],
                "selected_goals": ["muscle-gain"],
            })

            call_kwargs = mock_service.get_nutrition_data.call_args.kwargs
            query = call_kwargs["query"]
            assert query.dietaryPreferences == ["high-protein", "low-carb"]
            assert query.allergies == ["gluten"]
            assert query.selectedGoals == ["muscle-gain"]


class TestAnalyseFoodDescriptionTool:
    """Test analyse_food_description with text only."""

    def test_analyse_food_description_text_only(self):
        """User describes food in text - tool should call service and return nutrition data."""
        with patch("app.agent.tools.NutritionService") as mock_service:
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "response": {
                    "foodName": "Maggi Noodles",
                    "overallHealthScore": 5,
                    "calories": 270,
                },
                "status": 200,
                "message": "SUCCESS",
            }
            mock_service.log_food_nutrition_data_using_description.return_value = mock_response

            result = analyse_food_description.invoke({
                "food_description": "1 pack of maggi noodles",
                "dietary_preferences": ["vegetarian"],
                "allergies": ["nuts"],
                "selected_goals": ["weight-loss"],
            })

            mock_service.log_food_nutrition_data_using_description.assert_called_once()
            call_args = mock_service.log_food_nutrition_data_using_description.call_args
            payload = call_args.args[0] if call_args.args else call_args.kwargs.get("payload")
            assert payload.food_description == "1 pack of maggi noodles"
            assert result["response"]["foodName"] == "Maggi Noodles"

    def test_analyse_food_description_empty_profile(self):
        """When no profile info provided, defaults are used."""
        with patch("app.agent.tools.NutritionService") as mock_service:
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "response": {"foodName": "Burger"},
                "status": 200,
                "message": "SUCCESS",
            }
            mock_service.log_food_nutrition_data_using_description.return_value = mock_response

            analyse_food_description.invoke({
                "food_description": "cheese burger",
            })

            call_args = mock_service.log_food_nutrition_data_using_description.call_args
            payload = call_args.args[0] if call_args.args else call_args.kwargs.get("payload")
            assert payload.dietaryPreferences == []
            assert payload.allergies == []
            assert payload.selectedGoals == []


class TestAnalyseWithBothImageAndText:
    """Test scenarios where user provides both image and text description."""

    def test_image_with_text_description(self):
        """Image URL combined with text description for enhanced analysis."""
        with patch("app.agent.tools.NutritionService") as mock_service:
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "response": {
                    "foodName": "Pasta Primavera",
                    "overallHealthScore": 7,
                },
                "status": 200,
                "message": "SUCCESS",
            }
            mock_service.get_nutrition_data.return_value = mock_response

            result = analyse_image.invoke({
                "image_url": "https://example.com/pasta.jpg",
                "food_description": "pasta with vegetables and olive oil",
                "dietary_preferences": ["mediterranean", "vegetarian"],
                "allergies": ["gluten"],
                "selected_goals": ["heart-health"],
            })

            call_kwargs = mock_service.get_nutrition_data.call_args.kwargs
            query = call_kwargs["query"]
            assert query.imageUrl == "https://example.com/pasta.jpg"
            assert "vegetables" in query.food_description.lower()
            assert "mediterranean" in query.dietaryPreferences
            assert result["response"]["foodName"] == "Pasta Primavera"

    def test_food_description_with_reference_image_url(self):
        """Food description with reference image URL for cross-checking."""
        with patch("app.agent.tools.NutritionService") as mock_service:
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "response": {"foodName": "Grilled Salmon"},
                "status": 200,
                "message": "SUCCESS",
            }
            mock_service.log_food_nutrition_data_using_description.return_value = mock_response

            analyse_food_description.invoke({
                "food_description": "grilled salmon with lemon and herbs",
                "image_url": "https://example.com/salmon.jpg",
                "dietary_preferences": ["keto", "high-protein"],
                "selected_goals": ["weight-loss", "muscle-gain"],
            })

            call_args = mock_service.log_food_nutrition_data_using_description.call_args
            payload = call_args.args[0] if call_args.args else call_args.kwargs.get("payload")
            assert "salmon" in payload.food_description.lower()
            assert payload.imageUrl == "https://example.com/salmon.jpg"
            assert payload.dietaryPreferences == ["keto", "high-protein"]