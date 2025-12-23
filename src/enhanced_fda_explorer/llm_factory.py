"""
LLM Factory - Central factory for creating LLM instances across providers.
"""
import os
from typing import Optional
from langchain_core.language_models import BaseChatModel


class LLMFactory:
    """Central factory for creating LLM instances across providers."""

    PROVIDER_DEFAULTS = {
        "openrouter": "xiaomi/mimo-v2-flash:free",
        "bedrock": "anthropic.claude-3-haiku-20240307-v1:0",
        "ollama": "llama3.1",
    }

    @classmethod
    def create(
        cls,
        provider: str = "openrouter",
        model: Optional[str] = None,
        temperature: float = 0.1,
        **kwargs
    ) -> BaseChatModel:
        """
        Create an LLM instance for the specified provider.

        Args:
            provider: LLM provider ("openrouter", "bedrock", "ollama")
            model: Model name (provider-specific). If None, uses provider default.
            temperature: Sampling temperature (0.0-1.0)
            **kwargs: Additional provider-specific arguments

        Returns:
            BaseChatModel instance configured for the provider
        """
        model = model or cls.PROVIDER_DEFAULTS.get(provider)

        if provider == "openrouter":
            return cls._create_openrouter(model, temperature, **kwargs)
        elif provider == "bedrock":
            return cls._create_bedrock(model, temperature, **kwargs)
        elif provider == "ollama":
            return cls._create_ollama(model, temperature, **kwargs)
        else:
            raise ValueError(f"Unknown provider: {provider}. Supported: openrouter, bedrock, ollama")

    @classmethod
    def _create_openrouter(cls, model: str, temperature: float, **kwargs) -> BaseChatModel:
        """Create OpenRouter LLM via OpenAI-compatible API."""
        from langchain_openai import ChatOpenAI
        from .config import get_config

        config = get_config(validate_startup=False)
        api_key = (
            os.getenv("OPENROUTER_API_KEY")
            or os.getenv("AI_API_KEY")
            or config.ai.api_key
        )
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY or AI_API_KEY environment variable required")

        return ChatOpenAI(
            model=model,
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            temperature=temperature,
            max_tokens=kwargs.get("max_tokens"),
            timeout=kwargs.get("timeout"),
        )

    @classmethod
    def _create_bedrock(cls, model: str, temperature: float, **kwargs) -> BaseChatModel:
        """Create AWS Bedrock LLM using ChatBedrockConverse."""
        from langchain_aws import ChatBedrockConverse

        return ChatBedrockConverse(
            model=model,
            temperature=temperature,
            region_name=kwargs.get("region", os.getenv("AWS_DEFAULT_REGION", "us-east-1")),
        )

    @classmethod
    def _create_ollama(cls, model: str, temperature: float, **kwargs) -> BaseChatModel:
        """Create Ollama LLM for local models."""
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model,
            temperature=temperature,
            base_url=kwargs.get("base_url", "http://localhost:11434"),
        )

    @classmethod
    def list_providers(cls) -> list[str]:
        """List available providers."""
        return list(cls.PROVIDER_DEFAULTS.keys())

    @classmethod
    def get_default_model(cls, provider: str) -> str:
        """Get default model for a provider."""
        return cls.PROVIDER_DEFAULTS.get(provider, "")
