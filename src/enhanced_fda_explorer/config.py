"""
Configuration management for Enhanced FDA Explorer
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings


class OpenFDAConfig(BaseModel):
    """OpenFDA API configuration"""
    base_url: str = "https://api.fda.gov/"
    api_key: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    rate_limit_delay: float = 0.5
    user_agent: str = "Enhanced-FDA-Explorer/1.0"
    verify_ssl: bool = True


class AIConfig(BaseModel):
    """AI analysis configuration"""
    provider: str = "openai"  # openai, openrouter, anthropic
    model: str = "gpt-4"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 2000
    timeout: int = 60


class CacheConfig(BaseModel):
    """Caching configuration"""
    enabled: bool = True
    backend: str = "redis"  # redis, memory, file
    redis_url: Optional[str] = "redis://localhost:6379"
    ttl: int = 3600  # 1 hour default
    max_size: int = 1000  # For memory cache


class DatabaseConfig(BaseModel):
    """Database configuration"""
    url: str = "sqlite:///enhanced_fda_explorer.db"
    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 20


class AuthConfig(BaseModel):
    """Authentication configuration"""
    enabled: bool = False
    secret_key: str = "your-secret-key-change-this"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7


class APIConfig(BaseModel):
    """API server configuration"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"


class WebUIConfig(BaseModel):
    """Web UI configuration"""
    host: str = "0.0.0.0"
    port: int = 8501
    debug: bool = False
    theme: str = "light"  # light, dark, auto


class LoggingConfig(BaseModel):
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None
    max_bytes: int = 10485760  # 10MB
    backup_count: int = 5


class MonitoringConfig(BaseModel):
    """Monitoring and observability configuration"""
    enabled: bool = False
    prometheus_port: int = 9090
    jaeger_endpoint: Optional[str] = None
    log_level: str = "INFO"


class Config(BaseSettings):
    """Main configuration class"""
    
    # Environment
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # Component configurations
    openfda: OpenFDAConfig = Field(default_factory=OpenFDAConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    webui: WebUIConfig = Field(default_factory=WebUIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    
    # Application settings
    app_name: str = "Enhanced FDA Explorer"
    app_version: str = "1.0.0"
    description: str = "Next-generation FDA medical device data exploration platform"
    
    # Data settings
    default_sample_size: int = 100
    max_sample_size: int = 1000
    default_date_range_months: int = 12
    max_date_range_months: int = 60
    
    # Search settings
    search_timeout: int = 30
    max_concurrent_searches: int = 5
    enable_fuzzy_search: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_nested_delimiter = "__"
    
    @validator("environment")
    def validate_environment(cls, v):
        allowed = ["development", "testing", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of: {allowed}")
        return v
    
    @classmethod
    def from_file(cls, config_path: str) -> "Config":
        """Load configuration from YAML file"""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_file, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        
        return cls(**config_data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return self.dict()
    
    def save_to_file(self, config_path: str) -> None:
        """Save configuration to YAML file"""
        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)
    
    def get_openfda_client_config(self) -> Dict[str, Any]:
        """Get configuration for OpenFDA client"""
        return {
            "base_url": self.openfda.base_url,
            "api_key": self.openfda.api_key,
            "timeout": self.openfda.timeout,
            "max_retries": self.openfda.max_retries,
            "user_agent": self.openfda.user_agent,
            "verify_ssl": self.openfda.verify_ssl,
        }
    
    def get_ai_config(self) -> Dict[str, Any]:
        """Get configuration for AI analysis"""
        return {
            "provider": self.ai.provider,
            "model": self.ai.model,
            "api_key": self.ai.api_key,
            "base_url": self.ai.base_url,
            "temperature": self.ai.temperature,
            "max_tokens": self.ai.max_tokens,
            "timeout": self.ai.timeout,
        }


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance"""
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance"""
    global _config
    _config = config


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from file or environment"""
    if config_path:
        config = Config.from_file(config_path)
    else:
        config = Config()
    
    set_config(config)
    return config


# Default configuration paths
DEFAULT_CONFIG_PATHS = [
    "config/config.yaml",
    "config.yaml",
    "/etc/enhanced-fda-explorer/config.yaml",
    os.path.expanduser("~/.enhanced-fda-explorer/config.yaml"),
]


def auto_load_config() -> Config:
    """Auto-load configuration from default paths"""
    for path in DEFAULT_CONFIG_PATHS:
        if os.path.exists(path):
            return load_config(path)
    
    # No config file found, use defaults
    return load_config()