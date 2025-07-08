# Architecture

Enhanced FDA Explorer is designed as a modular, scalable platform for FDA medical device data exploration with AI-powered analysis capabilities.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Enhanced FDA Explorer                        │
├─────────────────────────────────────────────────────────────────┤
│                      User Interfaces                           │
├──────────────┬──────────────┬──────────────┬──────────────────┤
│   Web UI     │   REST API   │   CLI Tool   │   Python SDK     │
│ (Streamlit)  │  (FastAPI)   │   (Click)    │    (asyncio)     │
└──────────────┴──────────────┴──────────────┴──────────────────┘
├─────────────────────────────────────────────────────────────────┤
│                      Core Engine                               │
├──────────────┬──────────────┬──────────────┬──────────────────┤
│   Enhanced   │      AI      │    Config    │   Task Manager   │
│   Client     │   Analysis   │  Management  │   (Optional)     │
│              │    Engine    │              │                  │
└──────────────┴──────────────┴──────────────┴──────────────────┘
├─────────────────────────────────────────────────────────────────┤
│                       Data Layer                               │
├──────────────┬──────────────┬──────────────┬──────────────────┤
│   OpenFDA    │   Caching    │   Database   │   File Storage   │
│   API Client │  (Redis/Mem) │ (SQLite/PG)  │   (Optional)     │
└──────────────┴──────────────┴──────────────┴──────────────────┘
├─────────────────────────────────────────────────────────────────┤
│                    Infrastructure                              │
├──────────────┬──────────────┬──────────────┬──────────────────┤
│ Logging &    │ Auth & RBAC  │   Rate       │   Deployment     │
│ Monitoring   │ (Optional)   │  Limiting    │ (Docker/K8s)     │
└──────────────┴──────────────┴──────────────┴──────────────────┘
```

## Core Components

### 1. User Interfaces

#### Web UI (Streamlit)
- **Technology**: Streamlit framework
- **Purpose**: Interactive web dashboard for non-technical users
- **Features**:
  - Device search and analysis
  - Interactive visualizations
  - Report generation
  - Real-time data updates
- **Location**: `src/enhanced_fda_explorer/web.py`

#### REST API (FastAPI)
- **Technology**: FastAPI with async support
- **Purpose**: Programmatic access for applications and integrations
- **Features**:
  - RESTful endpoints
  - OpenAPI/Swagger documentation
  - Rate limiting
  - Input validation
- **Location**: `src/enhanced_fda_explorer/api.py`

#### CLI Tool (Click)
- **Technology**: Click framework with Rich formatting
- **Purpose**: Command-line interface for automation and scripting
- **Features**:
  - Comprehensive command set
  - Rich terminal output
  - Pipeline-friendly JSON output
  - Configuration management
- **Location**: `src/enhanced_fda_explorer/cli.py`

#### Python SDK
- **Technology**: Async Python with asyncio
- **Purpose**: Programmatic access for Python applications
- **Features**:
  - Async/await support
  - Type hints
  - Comprehensive error handling
  - Context manager support
- **Location**: `src/enhanced_fda_explorer/client.py`

### 2. Core Engine

#### Orchestrator (Conversational Agent)
- **Purpose**: Interpret user questions and orchestrate multi-endpoint device queries and AI responses.
- **Responsibilities**:
-   - Classify user intent for device-related queries (e.g. manufacturer lookup, location analysis).
-   - Plan and execute calls to appropriate OpenFDA device endpoints (events, recalls, classification, UDI, etc.).
-   - Aggregate and normalize results from multiple endpoints.
-   - Invoke AI Analysis Engine to generate coherent conversational answers.
- **LLM Provider Options**: OpenAI, OpenRouter, Anthropic, or local models (e.g. HuggingFace smolagents).
- **Location**: `src/enhanced_fda_explorer/orchestrator.py`

#### Enhanced Client
- **Purpose**: Orchestrates data retrieval and processing
- **Responsibilities**:
-   - OpenFDA API interaction
-   - Data validation and normalization
-   - Error handling and retries
-   - Rate limiting compliance
- **Key Classes**:
-   - `FDAExplorer`: Main client class
-   - `OpenFDAClient`: Low-level API client
-   - `DataNormalizer`: Data processing

#### AI Analysis Engine
- **Purpose**: Provides intelligent analysis and insights
- **Capabilities**:
  - Risk assessment scoring
  - Trend analysis
  - Comparative analysis
  - Natural language summaries
- **Supported Providers**:
  - OpenAI (GPT-4, GPT-3.5)
  - Anthropic (Claude)
  - OpenRouter (Multiple models)
  - HuggingFace smolagents (local agentic framework)
- **Location**: `src/enhanced_fda_explorer/ai.py`

#### Configuration Management
- **Purpose**: Centralized configuration handling
- **Features**:
  - Environment variable support
  - YAML configuration files
  - Pydantic validation
  - Hot reloading (development)
- **Location**: `src/enhanced_fda_explorer/config.py`

### 3. Data Layer

#### OpenFDA API Integration
- **Databases Supported**:
  - Device Events (adverse events)
  - Device Recalls
  - 510(k) Clearances
  - PMA Approvals
  - Device Classifications
  - UDI Database
- **Features**:
  - Automatic pagination
  - Field filtering
  - Date range queries
  - Complex search expressions

#### Caching Layer
- **Backends**:
  - Redis (production)
  - In-memory (development)
- **Features**:
  - Configurable TTL
  - Cache invalidation
  - Compression
  - Statistics tracking

#### Database Layer (Optional)
- **Backends**:
  - SQLite (development)
  - PostgreSQL (production)
- **Purpose**:
  - User data storage
  - Query history
  - Custom analytics
  - Audit trails

## Data Flow

### 1. Search Request Flow

```
User Input → Interface Layer → Core Engine → OpenFDA API
    ↓              ↓              ↓             ↓
Response ← UI/API/CLI ← FDAExplorer ← Client ← API Response
    ↓
AI Analysis (Optional)
    ↓
Final Response
```

### 2. Device Intelligence Flow

```
Device Name → Enhanced Client → Multiple API Calls
    ↓               ↓              ↓
Analysis ← Risk Engine ← Aggregated Data
    ↓               ↓
Trends ← Trend Engine ← Historical Data
    ↓               ↓
Report ← Report Engine ← Combined Analysis
```

### 3. Caching Strategy

```
Request → Cache Check → Hit? → Return Cached Data
    ↓         ↓          ↓
    No       Miss      API Call → Process → Cache → Return
```

## Security Architecture

### 1. API Key Management
- Environment variable storage
- No hardcoded credentials
- Rotation support
- Audit logging

### 2. Input Validation
- Pydantic models for all inputs
- SQL injection prevention
- XSS protection
- Rate limiting

### 3. Data Privacy
- No sensitive data storage
- PII filtering
- Secure transmission (HTTPS/TLS)
- Audit trails

## Scalability Considerations

### 1. Horizontal Scaling
- Stateless application design
- Load balancer compatible
- Shared cache and database
- Container-ready

### 2. Performance Optimization
- Async/await throughout
- Connection pooling
- Result caching
- Lazy loading

### 3. Resource Management
- Memory-efficient streaming
- Configurable timeouts
- Circuit breakers
- Graceful degradation

## Deployment Architecture

### 1. Development
```
Developer Machine
├── Python Virtual Environment
├── Local SQLite Database
├── In-memory Cache
└── Direct API Calls
```

### 2. Production (Docker)
```
Load Balancer
├── App Container 1 (Web UI + API)
├── App Container 2 (Web UI + API)
└── App Container N (Web UI + API)
    ↓
Shared Services
├── Redis Cache Cluster
├── PostgreSQL Database
└── Monitoring Stack
```

### 3. Production (Kubernetes)
```
Ingress Controller
├── FDA Explorer Deployment (3 replicas)
├── Redis StatefulSet
├── PostgreSQL StatefulSet
├── ConfigMaps & Secrets
└── Monitoring (Prometheus/Grafana)
```

## Technology Stack

### Backend
- **Python 3.8+**: Core language
- **FastAPI**: REST API framework
- **Streamlit**: Web UI framework
- **Click**: CLI framework
- **asyncio**: Asynchronous programming
- **aiohttp**: Async HTTP client
- **Pydantic**: Data validation
- **SQLAlchemy**: Database ORM

### Data & Caching
- **Redis**: Caching layer
- **PostgreSQL**: Primary database
- **SQLite**: Development database

### AI & ML
- **OpenAI API**: GPT models
- **Anthropic API**: Claude models
- **OpenRouter**: Multiple model access

### Infrastructure
- **Docker**: Containerization
- **Kubernetes**: Orchestration
- **nginx**: Load balancing
- **Prometheus**: Monitoring
- **Grafana**: Visualization

### Development
- **pytest**: Testing framework
- **black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **pre-commit**: Git hooks

## Design Patterns

### 1. Repository Pattern
```python
class FDARepository:
    async def search_devices(self, query: str) -> List[Device]:
        # Abstract data access
```

### 2. Factory Pattern
```python
class AIProviderFactory:
    @staticmethod
    def create(provider: str) -> AIProvider:
        # Create appropriate AI provider
```

### 3. Observer Pattern
```python
class EventManager:
    def notify_subscribers(self, event: Event):
        # Notify all registered observers
```

### 4. Strategy Pattern
```python
class CacheStrategy:
    async def get(self, key: str) -> Optional[Any]:
        # Different caching strategies
```

## Configuration Architecture

### 1. Configuration Hierarchy
```
1. Command-line arguments (highest priority)
2. Environment variables
3. Configuration file (.env, config.yaml)
4. Default values (lowest priority)
```

### 2. Configuration Structure
```yaml
app:
  name: "Enhanced FDA Explorer"
  version: "1.0.0"
  environment: "production"

api:
  host: "0.0.0.0"
  port: 8000
  workers: 4

openfda:
  api_key: "${FDA_API_KEY}"
  timeout: 30
  max_retries: 3

ai:
  provider: "openai"
  model: "gpt-4"
  api_key: "${AI_API_KEY}"

database:
  url: "${DATABASE_URL}"
  pool_size: 10

cache:
  type: "redis"
  url: "${REDIS_URL}"
  ttl: 3600

logging:
  level: "INFO"
  format: "json"
```

## Error Handling Architecture

### 1. Error Hierarchy
```python
FDAExplorerError
├── APIError
│   ├── AuthenticationError
│   ├── RateLimitError
│   └── TimeoutError
├── ValidationError
├── ConfigurationError
└── CacheError
```

### 2. Error Propagation
```
Low-level Error → Service Layer → Business Logic → Interface Layer
      ↓              ↓              ↓              ↓
   Log Error → Transform Error → Add Context → User-friendly Message
```

## Monitoring & Observability

### 1. Metrics
- Request latency
- Error rates
- API quotas
- Cache hit rates
- Database performance

### 2. Logging
- Structured JSON logging
- Correlation IDs
- Performance timings
- Error details
- Audit trails

### 3. Health Checks
- API endpoint health
- Database connectivity
- Cache availability
- External service status

## Future Architecture Considerations

### 1. Microservices Migration
- Search Service
- AI Analysis Service
- Report Generation Service
- User Management Service

### 2. Event-Driven Architecture
- Message queues (RabbitMQ/Kafka)
- Event sourcing
- CQRS pattern

### 3. Machine Learning Pipeline
- Data preprocessing
- Model training
- Feature engineering
- Prediction serving

This architecture provides a solid foundation for current needs while maintaining flexibility for future enhancements and scaling requirements.