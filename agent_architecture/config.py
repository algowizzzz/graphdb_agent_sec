"""
Unified Configuration System for the SEC Graph Agent

This module provides a centralized and flexible way to manage all configurations 
for the agent, including LLM providers, database connections, and embedding models.

It supports loading sensitive data (like API keys) from a .env file and allows
for easy switching between different LLM providers (OpenAI, Anthropic, Ollama, Google).
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# --- Data Classes for Type-Safe Configuration ---

@dataclass
class LLMConfig:
    """Configuration for the Language Model client."""
    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None  # For Ollama

@dataclass
class DatabaseConfig:
    """Configuration for the Neo4j database connection."""
    uri: str
    user: str
    password: str

@dataclass
class AgentConfig:
    """Top-level configuration for the agent."""
    llm: LLMConfig
    database: DatabaseConfig
    embedding_model: str

# --- Provider-Specific Model Mappings ---

# Defines available models for each provider, with tiers like "default", "fast", "powerful"
MODEL_MAPPINGS = {
    "openai": {
        "default": "gpt-4o",
        "fast": "gpt-4o-mini",
        "powerful": "gpt-4o",
    },
    "anthropic": {
        "default": "claude-3-haiku-20240307",
        "fast": "claude-3-haiku-20240307",
        "powerful": "claude-3-sonnet-20240229",
    },
    "ollama": {
        "default": "llama3:latest",
        "fast": "llama3:8b",
        "powerful": "llama3:70b",
    },
    "google": {
        "default": "gemini-1.5-pro-latest",
        "fast": "gemini-1.5-flash-latest",
        "powerful": "gemini-1.5-pro-latest",
    }
}

# --- Main Configuration Logic ---

class ConfigManager:
    """Manages the retrieval and validation of configurations."""

    @staticmethod
    def get_llm_config(provider: str, model_tier: str) -> LLMConfig:
        """Builds the LLM configuration for a given provider and tier."""
        provider = provider.lower()
        model_tier = model_tier.lower()

        if provider not in MODEL_MAPPINGS:
            raise ValueError(f"Invalid LLM provider: '{provider}'. Available: {list(MODEL_MAPPINGS.keys())}")
        
        models = MODEL_MAPPINGS[provider]
        if model_tier not in models:
            raise ValueError(f"Invalid model tier: '{model_tier}'. Available for {provider}: {list(models.keys())}")

        model_name = models[model_tier]
        
        # API keys are stored in environment variables (e.g., OPENAI_API_KEY)
        api_key_name = f"{provider.upper()}_API_KEY"
        api_key = os.getenv(api_key_name)
        
        # Special handling for Ollama base URL
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") if provider == "ollama" else None

        return LLMConfig(provider=provider, model=model_name, api_key=api_key, base_url=base_url)

    @staticmethod
    def get_database_config() -> DatabaseConfig:
        """Builds the database configuration from environment variables."""
        return DatabaseConfig(
            uri=os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password")
        )

    @staticmethod
    def validate_config(config: AgentConfig) -> bool:
        """
        Validates the configuration, ensuring API keys are present for cloud providers.
        """
        if config.llm.provider != "ollama":
            if not config.llm.api_key:
                print(f"⚠️  Warning: API key for {config.llm.provider} not found. Please set {config.llm.provider.upper()}_API_KEY in your .env file.")
                return False
        return True

    @staticmethod
    def list_available_providers() -> dict:
        """Returns the dictionary of available providers and their model tiers."""
        return MODEL_MAPPINGS

def get_config(provider: str, model_tier: str = "default") -> AgentConfig:
    """
    High-level function to get the complete, validated agent configuration.
    
    Args:
        provider: The LLM provider to use (e.g., 'openai', 'anthropic').
        model_tier: The desired model tier (e.g., 'default', 'fast').

    Returns:
        A fully populated AgentConfig object.
    """
    llm_config = ConfigManager.get_llm_config(provider, model_tier)
    db_config = ConfigManager.get_database_config()
    
    # Using a standard, high-quality embedding model
    embedding_model = "sentence-transformers/all-mpnet-base-v2"

    return AgentConfig(
        llm=llm_config,
        database=db_config,
        embedding_model=embedding_model
    ) 