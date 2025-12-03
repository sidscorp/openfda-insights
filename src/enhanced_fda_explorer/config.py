"""
Configuration management for Enhanced FDA Explorer
"""

import os
import re
import yaml
from pathlib import Path
from typing import Any, Dict, Optional, List
from urllib.parse import urlparse
try:
    from pydantic import BaseModel, Field, validator, root_validator
    from pydantic_settings import BaseSettings
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseModel, Field, validator, root_validator, BaseSettings


class OpenFDAConfig(BaseModel):
    """OpenFDA API configuration"""
    base_url: str = Field(default="https://api.fda.gov/", env="FDA_BASE_URL")
    api_key: Optional[str] = Field(default=None, env="FDA_API_KEY")
    timeout: int = Field(default=30, env="FDA_TIMEOUT", ge=1, le=300)
    max_retries: int = Field(default=3, env="FDA_MAX_RETRIES", ge=0, le=10)
    rate_limit_delay: float = Field(default=0.5, env="FDA_RATE_LIMIT_DELAY", ge=0.0, le=10.0)
    user_agent: str = Field(default="Enhanced-FDA-Explorer/1.0", env="FDA_USER_AGENT")
    verify_ssl: bool = Field(default=True, env="FDA_VERIFY_SSL")
    
    @validator("base_url")
    def validate_base_url(cls, v):
        """Validate FDA base URL format"""
        if not v:
            raise ValueError("FDA base URL cannot be empty")
        
        parsed = urlparse(v)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("FDA base URL must be a valid URL with scheme and domain")
        
        if parsed.scheme not in ["http", "https"]:
            raise ValueError("FDA base URL must use http or https protocol")
        
        return v.rstrip("/") + "/"  # Ensure trailing slash
    
    @validator("api_key")
    def validate_api_key(cls, v):
        """Validate FDA API key format"""
        if v and len(v.strip()) < 10:
            raise ValueError("FDA API key appears to be too short")
        return v
    
    @validator("user_agent")
    def validate_user_agent(cls, v):
        """Validate user agent string"""
        if not v or len(v.strip()) < 5:
            raise ValueError("User agent must be a meaningful string")
        return v


class AIConfig(BaseModel):
    """AI analysis configuration"""
    provider: str = Field(default="openai", env="AI_PROVIDER")
    model: str = Field(default="gpt-4", env="AI_MODEL")
    api_key: Optional[str] = Field(default=None, env="AI_API_KEY")
    base_url: Optional[str] = Field(default=None, env="AI_BASE_URL")
    temperature: float = Field(default=0.3, env="AI_TEMPERATURE", ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, env="AI_MAX_TOKENS", ge=1, le=32000)
    timeout: int = Field(default=60, env="AI_TIMEOUT", ge=1, le=600)
    
    @validator("provider")
    def validate_provider(cls, v):
        """Validate AI provider"""
        allowed_providers = ["openai", "anthropic", "openrouter", "huggingface"]
        if v not in allowed_providers:
            raise ValueError(f"AI provider must be one of: {allowed_providers}")
        return v
    
    @validator("api_key")
    def validate_api_key(cls, v, values):
        """Validate AI API key when provider requires it"""
        if not v:
            return v
        
        provider = values.get("provider", "openai")
        
        # Basic length validation based on provider
        min_lengths = {
            "openai": 40,
            "anthropic": 40, 
            "openrouter": 30,
            "huggingface": 30
        }
        
        min_length = min_lengths.get(provider, 20)
        if len(v.strip()) < min_length:
            raise ValueError(f"API key for {provider} appears to be too short (minimum {min_length} characters)")
        
        # Provider-specific validation
        if provider == "openai" and not v.startswith("sk-"):
            raise ValueError("OpenAI API key must start with 'sk-'")
        elif provider == "anthropic" and not v.startswith("sk-ant-"):
            raise ValueError("Anthropic API key must start with 'sk-ant-'")
        
        return v
    
    @validator("base_url")
    def validate_base_url(cls, v):
        """Validate AI base URL format"""
        if not v:
            return v
        
        parsed = urlparse(v)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("AI base URL must be a valid URL with scheme and domain")
        
        if parsed.scheme not in ["http", "https"]:
            raise ValueError("AI base URL must use http or https protocol")
        
        return v.rstrip("/")
    
    @validator("model")
    def validate_model(cls, v, values):
        """Validate model name for provider"""
        if not v:
            raise ValueError("AI model cannot be empty")
        
        provider = values.get("provider", "openai")
        
        # Provider-specific model validation
        valid_models = {
            "openai": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4o", "gpt-4o-mini"],
            "anthropic": ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"],
            "openrouter": [],  # OpenRouter supports many models
            "huggingface": []  # HuggingFace supports many models
        }
        
        if provider in valid_models and valid_models[provider] and v not in valid_models[provider]:
            raise ValueError(f"Model '{v}' is not supported for provider '{provider}'. Valid models: {valid_models[provider]}")
        
        return v


class CacheConfig(BaseModel):
    """Caching configuration"""
    enabled: bool = Field(default=True, env="CACHE_ENABLED")
    backend: str = Field(default="memory", env="CACHE_BACKEND")
    redis_url: Optional[str] = Field(default="redis://localhost:6379", env="REDIS_URL")
    ttl: int = Field(default=3600, env="CACHE_TTL", ge=1, le=86400)  # 1 second to 1 day
    max_size: int = Field(default=1000, env="CACHE_MAX_SIZE", ge=1, le=100000)
    
    @validator("backend")
    def validate_backend(cls, v):
        """Validate cache backend"""
        allowed_backends = ["redis", "memory", "file"]
        if v not in allowed_backends:
            raise ValueError(f"Cache backend must be one of: {allowed_backends}")
        return v
    
    @validator("redis_url")
    def validate_redis_url(cls, v, values):
        """Validate Redis URL when Redis backend is used"""
        if not v:
            return v
        
        backend = values.get("backend", "memory")
        if backend == "redis":
            if not v:
                raise ValueError("Redis URL is required when using Redis cache backend")
            
            parsed = urlparse(v)
            if parsed.scheme not in ["redis", "rediss"]:
                raise ValueError("Redis URL must start with 'redis://' or 'rediss://'")
            
            if not parsed.hostname:
                raise ValueError("Redis URL must include a hostname")
        
        return v
    
    @root_validator(skip_on_failure=True)
    def validate_redis_config(cls, values):
        """Validate Redis configuration consistency"""
        backend = values.get("backend")
        redis_url = values.get("redis_url")
        
        if backend == "redis" and not redis_url:
            raise ValueError("Redis URL must be provided when using Redis cache backend")
        
        return values


class DatabaseConfig(BaseModel):
    """Database configuration"""
    url: str = Field(default="sqlite:///enhanced_fda_explorer.db", env="DATABASE_URL")
    echo: bool = Field(default=False, env="DATABASE_ECHO")
    pool_size: int = Field(default=10, env="DATABASE_POOL_SIZE", ge=1, le=100)
    max_overflow: int = Field(default=20, env="DATABASE_MAX_OVERFLOW", ge=0, le=100)
    
    @validator("url")
    def validate_database_url(cls, v):
        """Validate database URL format"""
        if not v:
            raise ValueError("Database URL cannot be empty")
        
        # Basic URL validation
        if "://" not in v:
            raise ValueError("Database URL must include a protocol (e.g., sqlite://, postgresql://)")
        
        scheme = v.split("://")[0]
        supported_schemes = ["sqlite", "postgresql", "mysql", "oracle"]
        
        if scheme not in supported_schemes:
            raise ValueError(f"Database scheme '{scheme}' not supported. Use one of: {supported_schemes}")
        
        # SQLite-specific validation
        if scheme == "sqlite":
            if not (v.startswith("sqlite:///") or v == "sqlite:///:memory:"):
                raise ValueError("SQLite URL must start with 'sqlite:///' or be 'sqlite:///:memory:'")
        
        # PostgreSQL-specific validation
        elif scheme == "postgresql":
            parsed = urlparse(v)
            if not parsed.hostname:
                raise ValueError("PostgreSQL URL must include a hostname")
        
        return v


class AuthConfig(BaseModel):
    """Authentication configuration"""
    enabled: bool = Field(default=False, env="AUTH_ENABLED")
    secret_key: str = Field(default="your-secret-key-change-this", env="AUTH_SECRET_KEY")
    algorithm: str = Field(default="HS256", env="AUTH_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", ge=1, le=1440)
    refresh_token_expire_days: int = Field(default=7, env="AUTH_REFRESH_TOKEN_EXPIRE_DAYS", ge=1, le=365)
    
    @validator("secret_key")
    def validate_secret_key(cls, v, values):
        """Validate secret key strength"""
        enabled = values.get("enabled", False)
        
        if enabled and v == "your-secret-key-change-this":
            raise ValueError("Default secret key must be changed when authentication is enabled")
        
        if enabled and len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters long when authentication is enabled")
        
        # Check for reasonable complexity when auth is enabled
        if enabled:
            if v.isalnum() or v.islower() or v.isupper():
                raise ValueError("Secret key should contain mixed case, numbers, and special characters when authentication is enabled")
        
        return v
    
    @validator("algorithm")
    def validate_algorithm(cls, v):
        """Validate JWT algorithm"""
        allowed_algorithms = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]
        if v not in allowed_algorithms:
            raise ValueError(f"Algorithm must be one of: {allowed_algorithms}")
        return v


class APIConfig(BaseModel):
    """API server configuration"""
    host: str = Field(default="0.0.0.0", env="API_HOST")
    port: int = Field(default=8000, env="API_PORT", ge=1, le=65535)
    debug: bool = Field(default=False, env="API_DEBUG")
    docs_url: str = Field(default="/docs", env="API_DOCS_URL")
    redoc_url: str = Field(default="/redoc", env="API_REDOC_URL")
    openapi_url: str = Field(default="/openapi.json", env="API_OPENAPI_URL")
    
    @validator("host")
    def validate_host(cls, v):
        """Validate host address"""
        if not v:
            raise ValueError("API host cannot be empty")
        
        # Basic validation for common host formats
        if v not in ["0.0.0.0", "127.0.0.1", "localhost"] and not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", v):
            # Allow domain names and other valid formats
            if not re.match(r"^[a-zA-Z0-9.-]+$", v):
                raise ValueError("Host must be a valid IP address, domain name, or 'localhost'")
        
        return v
    
    @validator("docs_url", "redoc_url", "openapi_url")
    def validate_url_paths(cls, v):
        """Validate URL paths"""
        if not v.startswith("/"):
            raise ValueError("URL paths must start with '/'")
        return v


class WebUIConfig(BaseModel):
    """Web UI configuration"""
    host: str = Field(default="0.0.0.0", env="WEBUI_HOST")
    port: int = Field(default=8501, env="WEBUI_PORT", ge=1, le=65535)
    debug: bool = Field(default=False, env="WEBUI_DEBUG")
    theme: str = Field(default="light", env="WEBUI_THEME")
    
    @validator("host")
    def validate_host(cls, v):
        """Validate host address"""
        if not v:
            raise ValueError("WebUI host cannot be empty")
        
        # Basic validation for common host formats
        if v not in ["0.0.0.0", "127.0.0.1", "localhost"] and not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", v):
            # Allow domain names and other valid formats
            if not re.match(r"^[a-zA-Z0-9.-]+$", v):
                raise ValueError("Host must be a valid IP address, domain name, or 'localhost'")
        
        return v
    
    @validator("theme")
    def validate_theme(cls, v):
        """Validate UI theme"""
        allowed_themes = ["light", "dark", "auto"]
        if v not in allowed_themes:
            raise ValueError(f"Theme must be one of: {allowed_themes}")
        return v


class LoggingConfig(BaseModel):
    """Logging configuration"""
    level: str = Field(default="INFO", env="LOG_LEVEL")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", env="LOG_FORMAT")
    file: Optional[str] = Field(default=None, env="LOG_FILE")
    max_bytes: int = Field(default=10485760, env="LOG_MAX_BYTES", ge=1024, le=1073741824)  # 1KB to 1GB
    backup_count: int = Field(default=5, env="LOG_BACKUP_COUNT", ge=0, le=50)
    
    @validator("level")
    def validate_level(cls, v):
        """Validate logging level"""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            raise ValueError(f"Log level must be one of: {allowed_levels}")
        return v.upper()
    
    @validator("file")
    def validate_file(cls, v):
        """Validate log file path"""
        if v:
            # Ensure parent directory exists or can be created
            log_path = Path(v)
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
            except (OSError, PermissionError) as e:
                raise ValueError(f"Cannot create log file directory: {e}")
        return v


class MonitoringConfig(BaseModel):
    """Monitoring and observability configuration"""
    enabled: bool = Field(default=False, env="MONITORING_ENABLED")
    prometheus_port: int = Field(default=9090, env="PROMETHEUS_PORT", ge=1, le=65535)
    jaeger_endpoint: Optional[str] = Field(default=None, env="JAEGER_ENDPOINT")
    log_level: str = Field(default="INFO", env="MONITORING_LOG_LEVEL")
    
    @validator("jaeger_endpoint")
    def validate_jaeger_endpoint(cls, v):
        """Validate Jaeger endpoint URL"""
        if v:
            parsed = urlparse(v)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Jaeger endpoint must be a valid URL with scheme and domain")
            
            if parsed.scheme not in ["http", "https"]:
                raise ValueError("Jaeger endpoint must use http or https protocol")
        
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate monitoring log level"""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            raise ValueError(f"Monitoring log level must be one of: {allowed_levels}")
        return v.upper()


class Config(BaseSettings):
    """Main configuration class with comprehensive validation"""
    
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
    app_name: str = Field(default="Enhanced FDA Explorer", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    description: str = Field(default="Next-generation FDA medical device data exploration platform", env="APP_DESCRIPTION")
    
    # Data settings
    default_sample_size: int = Field(default=100, env="DEFAULT_SAMPLE_SIZE", ge=1, le=10000)
    max_sample_size: int = Field(default=1000, env="MAX_SAMPLE_SIZE", ge=1, le=100000)
    default_date_range_months: int = Field(default=12, env="DEFAULT_DATE_RANGE_MONTHS", ge=1, le=120)
    max_date_range_months: int = Field(default=60, env="MAX_DATE_RANGE_MONTHS", ge=1, le=600)

    # GUDID Database settings
    gudid_db_path: str = Field(
        default="/root/projects/analytics-projects/shared-data/gudid_full.db",
        env="GUDID_DB_PATH"
    )
    
    # Search settings
    search_timeout: int = Field(default=30, env="SEARCH_TIMEOUT", ge=1, le=300)
    max_concurrent_searches: int = Field(default=5, env="MAX_CONCURRENT_SEARCHES", ge=1, le=50)
    enable_fuzzy_search: bool = Field(default=True, env="ENABLE_FUZZY_SEARCH")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_nested_delimiter = "__"
        validate_assignment = True
        extra = "ignore"  # Allow extra fields from .env
    
    @validator("environment")
    def validate_environment(cls, v):
        """Validate environment setting"""
        allowed = ["development", "testing", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of: {allowed}")
        return v
    
    @validator("max_sample_size")
    def validate_max_sample_size(cls, v, values):
        """Ensure max_sample_size is greater than default_sample_size"""
        default_size = values.get("default_sample_size", 100)
        if v < default_size:
            raise ValueError("max_sample_size must be greater than or equal to default_sample_size")
        return v
    
    @validator("max_date_range_months")
    def validate_max_date_range_months(cls, v, values):
        """Ensure max_date_range_months is greater than default_date_range_months"""
        default_range = values.get("default_date_range_months", 12)
        if v < default_range:
            raise ValueError("max_date_range_months must be greater than or equal to default_date_range_months")
        return v
    
    @root_validator(skip_on_failure=True)
    def validate_port_conflicts(cls, values):
        """Validate that API and WebUI ports don't conflict"""
        api_port = values.get("api", {}).port if hasattr(values.get("api", {}), 'port') else values.get("api", {}).get("port", 8000)
        webui_port = values.get("webui", {}).port if hasattr(values.get("webui", {}), 'port') else values.get("webui", {}).get("port", 8501)
        prometheus_port = values.get("monitoring", {}).prometheus_port if hasattr(values.get("monitoring", {}), 'prometheus_port') else values.get("monitoring", {}).get("prometheus_port", 9090)
        
        # Extract actual port values from config objects
        if hasattr(values.get("api"), 'port'):
            api_port = values.get("api").port
        if hasattr(values.get("webui"), 'port'):
            webui_port = values.get("webui").port
        if hasattr(values.get("monitoring"), 'prometheus_port'):
            prometheus_port = values.get("monitoring").prometheus_port
        
        ports = [api_port, webui_port, prometheus_port]
        if len(ports) != len(set(ports)):
            raise ValueError(f"Port conflict detected. API, WebUI, and Prometheus ports must be different: {ports}")
        
        return values
    
    @root_validator(skip_on_failure=True)
    def validate_ai_requirements(cls, values):
        """Validate AI configuration requirements"""
        ai_config = values.get("ai")
        
        if ai_config and hasattr(ai_config, 'provider'):
            provider = ai_config.provider
            api_key = ai_config.api_key
            
            # Warn about missing API key for certain operations
            if provider in ["openai", "anthropic", "openrouter"] and not api_key:
                # Don't fail validation, but this will be checked in startup validation
                pass
        
        return values
    
    def validate_startup(self, strict: bool = False) -> List[str]:
        """
        Validate configuration at startup with comprehensive checks.
        
        Args:
            strict: If True, treat warnings as errors
            
        Returns:
            List of warning/error messages
        """
        issues = []
        
        # Environment-specific validation
        if self.environment == "production":
            # Production-specific checks
            if self.auth.enabled and self.auth.secret_key == "your-secret-key-change-this":
                issues.append("CRITICAL: Default secret key must be changed in production")
            
            if self.debug:
                issues.append("WARNING: Debug mode should be disabled in production")
            
            if not self.openfda.verify_ssl:
                issues.append("WARNING: SSL verification should be enabled in production")
        
        # AI configuration validation
        # Check both nested config and direct env vars (AI_API_KEY, OPENROUTER_API_KEY)
        ai_key = self.ai.api_key or os.getenv("AI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        if self.ai.provider in ["openai", "anthropic", "openrouter"]:
            if not ai_key:
                issues.append(f"WARNING: No API key configured for AI provider '{self.ai.provider}'. AI features will be disabled.")
        
        # Cache configuration validation
        if self.cache.enabled and self.cache.backend == "redis":
            if not self.cache.redis_url:
                issues.append("ERROR: Redis URL is required when Redis cache is enabled")
        
        # Database connectivity (basic validation)
        if self.database.url.startswith("postgresql://"):
            # Could add database connectivity check here
            pass
        
        # Port availability checks
        ports_to_check = [self.api.port, self.webui.port]
        if self.monitoring.enabled:
            ports_to_check.append(self.monitoring.prometheus_port)
        
        # File permissions for logging
        if self.logging.file:
            try:
                log_path = Path(self.logging.file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                # Test write permissions
                test_file = log_path.parent / ".write_test"
                test_file.touch()
                test_file.unlink()
            except (OSError, PermissionError):
                issues.append(f"ERROR: Cannot write to log file location: {self.logging.file}")
        
        # Check for required vs recommended configurations
        if not self.openfda.api_key:
            issues.append("INFO: FDA API key not configured. Rate limiting may apply.")
        
        return issues
    
    def validate_and_fail_on_errors(self) -> None:
        """Validate configuration and raise exception if critical errors found"""
        issues = self.validate_startup(strict=False)
        
        errors = [issue for issue in issues if issue.startswith("ERROR") or issue.startswith("CRITICAL")]
        
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(errors)
            raise ValueError(error_msg)
    
    def get_validation_summary(self) -> Dict[str, List[str]]:
        """Get validation summary categorized by severity"""
        issues = self.validate_startup(strict=False)
        
        summary = {
            "critical": [issue for issue in issues if issue.startswith("CRITICAL")],
            "errors": [issue for issue in issues if issue.startswith("ERROR")],
            "warnings": [issue for issue in issues if issue.startswith("WARNING")],
            "info": [issue for issue in issues if issue.startswith("INFO")]
        }
        
        return summary
    
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


def get_config(validate_startup: bool = False) -> Config:
    """
    Get the global configuration instance
    
    Args:
        validate_startup: If True, run startup validation and fail on errors
    """
    global _config
    if _config is None:
        _config = Config()
        
        if validate_startup:
            _config.validate_and_fail_on_errors()
    
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance"""
    global _config
    _config = config


def load_config(config_path: Optional[str] = None, validate_startup: bool = False) -> Config:
    """
    Load configuration from file or environment
    
    Args:
        config_path: Path to configuration file (optional)
        validate_startup: If True, run startup validation and fail on errors
    """
    if config_path:
        config = Config.from_file(config_path)
    else:
        config = Config()
    
    if validate_startup:
        config.validate_and_fail_on_errors()
    
    set_config(config)
    return config


# Default configuration paths
DEFAULT_CONFIG_PATHS = [
    "config/config.yaml",
    "config.yaml",
    "/etc/enhanced-fda-explorer/config.yaml",
    os.path.expanduser("~/.enhanced-fda-explorer/config.yaml"),
]


def auto_load_config(validate_startup: bool = False) -> Config:
    """
    Auto-load configuration from default paths
    
    Args:
        validate_startup: If True, run startup validation and fail on errors
    """
    for path in DEFAULT_CONFIG_PATHS:
        if os.path.exists(path):
            return load_config(path, validate_startup=validate_startup)
    
    # No config file found, use defaults
    return load_config(validate_startup=validate_startup)


# Convenience functions for validation
def validate_current_config() -> Dict[str, List[str]]:
    """Validate current configuration and return summary"""
    config = get_config()
    return config.get_validation_summary()


def print_config_validation() -> None:
    """Print configuration validation summary to console"""
    summary = validate_current_config()
    
    if summary["critical"]:
        print("🚨 CRITICAL ISSUES:")
        for issue in summary["critical"]:
            print(f"  {issue}")
        print()
    
    if summary["errors"]:
        print("❌ ERRORS:")
        for issue in summary["errors"]:
            print(f"  {issue}")
        print()
    
    if summary["warnings"]:
        print("⚠️  WARNINGS:")
        for issue in summary["warnings"]:
            print(f"  {issue}")
        print()
    
    if summary["info"]:
        print("ℹ️  INFO:")
        for issue in summary["info"]:
            print(f"  {issue}")
        print()
    
    if not any(summary.values()):
        print("✅ Configuration validation passed with no issues!")


def ensure_valid_config() -> Config:
    """Ensure configuration is valid or raise exception"""
    config = get_config()
    config.validate_and_fail_on_errors()
    return config