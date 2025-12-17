"""
Centralized model initialization factory.
All LLM models are configured here to avoid hardcoded API keys.
"""

from langchain.chat_models import init_chat_model
# from config.settings import settings

import os

class ModelFactory:
    """Factory for creating LLM models with centralized configuration"""
    
    @staticmethod
    def _get_api_key():
        # Fallback to env var if settings not available
        return os.getenv("OPENAI_API_KEY", "dummy-key-for-tests")

    @staticmethod
    def get_receptor_model():
        """
        Get model for receptor node (data extraction).
        Uses Claude 3.5 Sonnet with temperature 0 for accuracy.
        """
        return init_chat_model(
            "openai:gpt-4o",
            temperature=0,
            api_key=ModelFactory._get_api_key()
        )

    @staticmethod
    def get_inquiry_model():
        """
        Get model for inquiry node (question generation).
        Uses GPT-4o with higher temperature for creativity.
        """
        return init_chat_model(
            "openai:gpt-4o",
            temperature=0.9,
            api_key=ModelFactory._get_api_key()
        )

    @staticmethod
    def get_recommendation_model():
        """
        Get model for recommendation node (medical assessment).
        Uses Claude Opus with low temperature for careful analysis.
        """
        return init_chat_model(
            "openai:gpt-4o",
            temperature=0.3,
            api_key=ModelFactory._get_api_key()
        )

    @staticmethod
    def get_urgency_recommendation_model():
        """
        Get model for urgency recommendation node (urgent triage).
        Uses GPT-4o with very low temperature for consistent, clear urgent messaging.
        Low temperature ensures predictable and accurate communication in critical situations.
        """
        return init_chat_model(
            "openai:gpt-4o",
            temperature=0.1,
            api_key=ModelFactory._get_api_key()
        )

