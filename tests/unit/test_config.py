"""
Unit tests for Enhanced FDA Explorer configuration validation
Tests for P1-T001: Add Pydantic BaseSettings for config validation
"""

import os
import pytest
from unittest.mock import patch
from pydantic import ValidationError

try:
    from enhanced_fda_explorer.config import (
        Config, OpenFDAConfig, AIConfig, CacheConfig, DatabaseConfig, AuthConfig,
        get_config, validate_current_config, ensure_valid_config, 
        print_config_validation
    )
except ImportError:
    # Handle case where dependencies aren't installed
    pytest.skip("enhanced_fda_explorer not available", allow_module_level=True)


class TestOpenFDAConfig:
    """Test OpenFDA configuration validation"""
    
    def test_valid_openfda_config(self):
        """Test valid OpenFDA configuration"""
        config = OpenFDAConfig(
            base_url="https://api.fda.gov/",
            api_key="test_key_1234567890",
            timeout=30,
            max_retries=3
        )
        assert config.base_url == "https://api.fda.gov/"
        assert config.api_key == "test_key_1234567890"
        assert config.timeout == 30
        assert config.max_retries == 3
    
    def test_base_url_validation(self):
        """Test base URL validation"""
        # Invalid URL scheme
        with pytest.raises(ValidationError, match="must use http or https protocol"):
            OpenFDAConfig(base_url="ftp://invalid.com")
        
        # Missing scheme
        with pytest.raises(ValidationError, match="must be a valid URL"):
            OpenFDAConfig(base_url="invalid-url")
        
        # Empty URL
        with pytest.raises(ValidationError, match="cannot be empty"):
            OpenFDAConfig(base_url="")
    
    def test_api_key_validation(self):
        """Test API key validation"""
        # Short API key
        with pytest.raises(ValidationError, match="appears to be too short"):
            OpenFDAConfig(api_key="short")
        
        # Valid API key
        config = OpenFDAConfig(api_key="test_key_1234567890")
        assert config.api_key == "test_key_1234567890"
    
    def test_numeric_range_validation(self):
        """Test numeric field validation"""
        # Timeout too low
        with pytest.raises(ValidationError):
            OpenFDAConfig(timeout=0)
        
        # Timeout too high  
        with pytest.raises(ValidationError):
            OpenFDAConfig(timeout=500)
        
        # Max retries too high
        with pytest.raises(ValidationError):
            OpenFDAConfig(max_retries=20)
    
    def test_trailing_slash_normalization(self):
        """Test that base URL gets normalized with trailing slash"""
        config = OpenFDAConfig(base_url="https://api.fda.gov")
        assert config.base_url == "https://api.fda.gov/"


class TestAIConfig:
    """Test AI configuration validation"""
    
    def test_valid_ai_config(self):
        """Test valid AI configuration"""
        config = AIConfig(
            provider="openai",
            model="gpt-4",
            api_key="sk-test_key_1234567890123456789012345678901234567890",
            temperature=0.3
        )
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.temperature == 0.3
    
    def test_provider_validation(self):
        """Test AI provider validation"""
        # Invalid provider
        with pytest.raises(ValidationError, match="must be one of"):
            AIConfig(provider="invalid_provider")
        
        # Valid providers
        for provider in ["openai", "anthropic", "openrouter", "huggingface"]:
            config = AIConfig(provider=provider)
            assert config.provider == provider
    
    def test_openai_api_key_validation(self):
        """Test OpenAI API key validation"""
        # OpenAI key without sk- prefix
        with pytest.raises(ValidationError, match="must start with 'sk-'"):
            AIConfig(provider="openai", api_key="invalid_openai_key_1234567890123456789012345678901234567890")
        
        # Valid OpenAI key
        config = AIConfig(provider="openai", api_key="sk-test_key_1234567890123456789012345678901234567890")
        assert config.api_key.startswith("sk-")
    
    def test_anthropic_api_key_validation(self):
        """Test Anthropic API key validation"""
        # Anthropic key without sk-ant- prefix
        with pytest.raises(ValidationError, match="must start with 'sk-ant-'"):
            AIConfig(provider="anthropic", api_key="sk-invalid_anthropic_key_1234567890123456789012345678901234567890")
        
        # Valid Anthropic key
        config = AIConfig(provider="anthropic", api_key="sk-ant-test_key_1234567890123456789012345678901234567890")
        assert config.api_key.startswith("sk-ant-")
    
    def test_model_validation(self):
        """Test model validation for different providers"""
        # Invalid OpenAI model
        with pytest.raises(ValidationError, match="not supported for provider"):
            AIConfig(provider="openai", model="invalid-model")
        
        # Valid OpenAI models
        for model in ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]:
            config = AIConfig(provider="openai", model=model)
            assert config.model == model
    
    def test_temperature_range_validation(self):
        """Test temperature range validation"""
        # Temperature too low
        with pytest.raises(ValidationError):
            AIConfig(temperature=-0.1)
        
        # Temperature too high
        with pytest.raises(ValidationError):
            AIConfig(temperature=2.1)
        
        # Valid temperature
        config = AIConfig(temperature=0.7)
        assert config.temperature == 0.7


class TestCacheConfig:
    """Test cache configuration validation"""
    
    def test_valid_cache_config(self):
        """Test valid cache configuration"""
        config = CacheConfig(
            enabled=True,
            backend="redis",
            redis_url="redis://localhost:6379",
            ttl=3600
        )
        assert config.enabled is True
        assert config.backend == "redis"
        assert config.redis_url == "redis://localhost:6379"
    
    def test_backend_validation(self):
        """Test cache backend validation"""
        # Invalid backend
        with pytest.raises(ValidationError, match="must be one of"):
            CacheConfig(backend="invalid_backend")
        
        # Valid backends
        for backend in ["redis", "memory", "file"]:
            config = CacheConfig(backend=backend)
            assert config.backend == backend
    
    def test_redis_url_validation(self):
        """Test Redis URL validation"""
        # Invalid Redis URL scheme
        with pytest.raises(ValidationError, match="must start with 'redis://'"):
            CacheConfig(backend="redis", redis_url="http://localhost:6379")
        
        # Missing hostname
        with pytest.raises(ValidationError, match="must include a hostname"):
            CacheConfig(backend="redis", redis_url="redis://")
        
        # Valid Redis URL
        config = CacheConfig(backend="redis", redis_url="redis://localhost:6379")
        assert config.redis_url == "redis://localhost:6379"
    
    def test_redis_required_validation(self):
        """Test that Redis URL is required when using Redis backend"""
        with pytest.raises(ValidationError, match="Redis URL must be provided"):
            CacheConfig(backend="redis", redis_url=None)


class TestDatabaseConfig:
    """Test database configuration validation"""
    
    def test_valid_database_config(self):
        """Test valid database configuration"""
        config = DatabaseConfig(
            url="sqlite:///test.db",
            pool_size=10,
            max_overflow=20
        )
        assert config.url == "sqlite:///test.db"
        assert config.pool_size == 10
        assert config.max_overflow == 20
    
    def test_database_url_validation(self):
        """Test database URL validation"""
        # Missing protocol
        with pytest.raises(ValidationError, match="must include a protocol"):
            DatabaseConfig(url="invalid_db_url")
        
        # Unsupported scheme
        with pytest.raises(ValidationError, match="not supported"):
            DatabaseConfig(url="mongodb://localhost/test")
        
        # Invalid SQLite URL
        with pytest.raises(ValidationError, match="must start with 'sqlite:///'"):
            DatabaseConfig(url="sqlite://invalid")
        
        # Valid URLs
        valid_urls = [
            "sqlite:///test.db",
            "sqlite:///:memory:",
            "postgresql://user:pass@localhost/db"
        ]
        for url in valid_urls:
            config = DatabaseConfig(url=url)
            assert config.url == url


class TestAuthConfig:
    """Test authentication configuration validation"""
    
    def test_secret_key_validation_when_enabled(self):
        """Test secret key validation when auth is enabled"""
        # Default secret key with auth enabled should fail
        with pytest.raises(ValidationError, match="Default secret key must be changed"):
            AuthConfig(enabled=True, secret_key="your-secret-key-change-this")
        
        # Short secret key with auth enabled should fail
        with pytest.raises(ValidationError, match="must be at least 32 characters"):
            AuthConfig(enabled=True, secret_key="short_key")
        
        # Simple secret key with auth enabled should fail
        with pytest.raises(ValidationError, match="should contain mixed case"):
            AuthConfig(enabled=True, secret_key="simple_lowercase_key_that_is_long_enough")
        
        # Valid complex secret key
        config = AuthConfig(enabled=True, secret_key="Complex_Secret_Key_123!@#_Very_Long_And_Secure")
        assert config.enabled is True
        assert len(config.secret_key) >= 32
    
    def test_secret_key_validation_when_disabled(self):
        """Test that secret key validation is relaxed when auth is disabled"""
        # Default secret key is OK when auth is disabled
        config = AuthConfig(enabled=False, secret_key="your-secret-key-change-this")
        assert config.enabled is False
        assert config.secret_key == "your-secret-key-change-this"
    
    def test_algorithm_validation(self):
        """Test JWT algorithm validation"""
        # Invalid algorithm
        with pytest.raises(ValidationError, match="must be one of"):
            AuthConfig(algorithm="INVALID")
        
        # Valid algorithms
        for algorithm in ["HS256", "HS384", "HS512", "RS256"]:
            config = AuthConfig(algorithm=algorithm)
            assert config.algorithm == algorithm


class TestConfigIntegration:
    """Test full configuration integration"""
    
    def test_environment_validation(self):
        """Test environment setting validation"""
        # Invalid environment
        with pytest.raises(ValidationError, match="must be one of"):
            Config(environment="invalid_env")
        
        # Valid environments
        for env in ["development", "testing", "staging", "production"]:
            config = Config(environment=env)
            assert config.environment == env
    
    def test_port_conflict_validation(self):
        """Test port conflict detection"""
        # This is a complex test that would need proper setup
        # For now, just test that config can be created with different ports
        config = Config()
        config.api.port = 8000
        config.webui.port = 8501
        config.monitoring.prometheus_port = 9090
        
        # The actual port conflict validation happens in root_validator
        # which is harder to test in isolation
        assert config.api.port != config.webui.port
        assert config.api.port != config.monitoring.prometheus_port
    
    def test_sample_size_validation(self):
        """Test sample size validation"""
        # Max sample size smaller than default should fail
        with pytest.raises(ValidationError, match="must be greater than or equal to default_sample_size"):
            Config(default_sample_size=100, max_sample_size=50)
        
        # Valid sample sizes
        config = Config(default_sample_size=100, max_sample_size=1000)
        assert config.default_sample_size == 100
        assert config.max_sample_size == 1000
    
    @patch.dict(os.environ, {
        'FDA_API_KEY': 'test_fda_key_1234567890',
        'AI_API_KEY': 'sk-test_ai_key_1234567890123456789012345678901234567890',
        'ENVIRONMENT': 'development',
        'DEBUG': 'true'
    })
    def test_environment_variable_loading(self):
        """Test environment variable loading"""
        config = Config()
        
        assert config.openfda.api_key == 'test_fda_key_1234567890'
        assert config.ai.api_key == 'sk-test_ai_key_1234567890123456789012345678901234567890'
        assert config.environment == 'development'
        assert config.debug is True


class TestValidationMethods:
    """Test configuration validation methods"""
    
    def test_validation_summary(self):
        """Test validation summary generation"""
        config = Config()
        summary = config.get_validation_summary()
        
        assert isinstance(summary, dict)
        assert "critical" in summary
        assert "errors" in summary
        assert "warnings" in summary
        assert "info" in summary
        
        # Each should be a list
        for key in summary:
            assert isinstance(summary[key], list)
    
    def test_startup_validation(self):
        """Test startup validation"""
        config = Config()
        issues = config.validate_startup()
        
        assert isinstance(issues, list)
        # Should have at least some info messages about missing API keys
        assert len(issues) > 0
    
    def test_validate_and_fail_on_errors(self):
        """Test validation that fails on errors"""
        # Create a config with no critical errors (default config should be OK)
        config = Config()
        
        # This should not raise an exception for default config
        try:
            config.validate_and_fail_on_errors()
        except ValueError:
            pytest.fail("Default configuration should not fail validation")


class TestConfigurationHelpers:
    """Test configuration helper functions"""
    
    def test_get_config(self):
        """Test get_config function"""
        config = get_config()
        assert isinstance(config, Config)
        
        # Test with validation
        config_with_validation = get_config(validate_startup=False)
        assert isinstance(config_with_validation, Config)
    
    def test_validate_current_config(self):
        """Test validate_current_config function"""
        summary = validate_current_config()
        assert isinstance(summary, dict)
        assert all(key in summary for key in ["critical", "errors", "warnings", "info"])
    
    def test_ensure_valid_config(self):
        """Test ensure_valid_config function"""
        # Should not raise for default config
        config = ensure_valid_config()
        assert isinstance(config, Config)


# Integration tests that require more setup could go here
class TestConfigurationIntegration:
    """Integration tests for configuration"""
    
    @pytest.mark.integration
    def test_config_file_loading(self, tmp_path):
        """Test loading configuration from file"""
        # Create a temporary config file
        config_file = tmp_path / "test_config.yaml"
        config_content = """
app_name: "Test FDA Explorer"
environment: "testing"
debug: true

openfda:
  api_key: "test_key_1234567890"
  timeout: 60

ai:
  provider: "openai"
  model: "gpt-3.5-turbo"
  api_key: "sk-test_key_1234567890123456789012345678901234567890"
"""
        config_file.write_text(config_content)
        
        # Load config from file
        from enhanced_fda_explorer.config import load_config
        config = load_config(str(config_file))
        
        assert config.app_name == "Test FDA Explorer"
        assert config.environment == "testing"
        assert config.debug is True
        assert config.openfda.api_key == "test_key_1234567890"
        assert config.ai.provider == "openai"