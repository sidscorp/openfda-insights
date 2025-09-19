"""
REST API for Enhanced FDA Explorer
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import uvicorn

from .core import FDAExplorer
from .config import get_config, ensure_valid_config
from .models import SearchRequest, SearchResponse
from .auth import AuthManager


# API Models
class SearchAPIRequest(BaseModel):
    """API request model for search"""
    query: str = Field(..., description="Search query")
    query_type: str = Field(default="device", description="Type of query")
    endpoints: Optional[List[str]] = Field(None, description="Endpoints to search")
    limit: int = Field(default=100, ge=1, le=1000, description="Result limit")
    include_ai_analysis: bool = Field(True, description="Include AI analysis")
    date_range_months: Optional[int] = Field(None, description="Date range in months")


class DeviceIntelligenceRequest(BaseModel):
    """API request model for device intelligence"""
    device_name: str = Field(..., description="Device name")
    lookback_months: int = Field(default=12, ge=1, le=60, description="Lookback period")
    include_risk_assessment: bool = Field(True, description="Include risk assessment")


class DeviceComparisonRequest(BaseModel):
    """API request model for device comparison"""
    device_names: List[str] = Field(..., description="Device names to compare")
    lookback_months: int = Field(default=12, ge=1, le=60, description="Lookback period")


class TrendAnalysisRequest(BaseModel):
    """API request model for trend analysis"""
    query: str = Field(..., description="Search query")
    time_periods: Optional[List[str]] = Field(None, description="Time periods")


class APIResponse(BaseModel):
    """Standard API response model"""
    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# Global explorer instance
explorer: Optional[FDAExplorer] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    global explorer
    
    # Startup
    logger = logging.getLogger(__name__)
    logger.info("Starting Enhanced FDA Explorer API...")
    
    try:
        # Validate configuration at startup
        config = ensure_valid_config()
        logger.info("Configuration validation passed")
        
        # Initialize explorer
        explorer = FDAExplorer(config)
        logger.info("Enhanced FDA Explorer API started successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start API: {e}")
        raise
    
    finally:
        # Shutdown
        if explorer:
            await explorer.close()
        logger.info("Enhanced FDA Explorer API stopped")


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    config = get_config()
    
    app = FastAPI(
        title="Enhanced FDA Explorer API",
        description="Next-generation FDA medical device data exploration platform",
        version="1.0.0",
        docs_url=config.api.docs_url,
        redoc_url=config.api.redoc_url,
        openapi_url=config.api.openapi_url,
        lifespan=lifespan
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3002", "https://portfolio.snambiar.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Authentication
    security = HTTPBearer() if config.auth.enabled else None
    auth_manager = AuthManager(config) if config.auth.enabled else None
    
    async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
        """Get current authenticated user"""
        if not auth_manager:
            return None
        return await auth_manager.get_current_user(credentials.credentials)
    
    # Routes
    
    @app.get("/", response_model=APIResponse)
    async def root():
        """Root endpoint"""
        return APIResponse(
            success=True,
            data={
                "name": "Enhanced FDA Explorer API",
                "version": "1.0.0",
                "description": "Next-generation FDA medical device data exploration platform",
                "endpoints": [
                    "/search",
                    "/device/intelligence",
                    "/device/compare",
                    "/trends",
                    "/health"
                ]
            },
            message="Enhanced FDA Explorer API is running"
        )
    
    @app.get("/health", response_model=APIResponse)
    async def health_check():
        """Health check endpoint"""
        return APIResponse(
            success=True,
            data={
                "status": "healthy",
                "api_version": "1.0.0",
                "timestamp": datetime.now().isoformat()
            },
            message="Service is healthy"
        )
    
    @app.post("/search", response_model=APIResponse)
    async def search_fda_data(
        request: SearchAPIRequest,
        background_tasks: BackgroundTasks,
        user=Depends(get_current_user) if config.auth.enabled else None
    ):
        """Search FDA data with AI analysis"""
        try:
            # Prepare date range if specified
            date_range = None
            if request.date_range_months:
                date_range = {
                    "start_date": datetime.now() - timedelta(days=request.date_range_months * 30),
                    "end_date": datetime.now()
                }
            
            # Perform search
            response = await explorer.search(
                query=request.query,
                query_type=request.query_type,
                endpoints=request.endpoints,
                limit=request.limit,
                include_ai_analysis=request.include_ai_analysis,
                date_range=date_range
            )
            
            # Convert DataFrames to JSON-serializable format
            serialized_results = {}
            for endpoint, df in response.results.items():
                serialized_results[endpoint] = df.to_dict('records')
            
            return APIResponse(
                success=True,
                data={
                    "query": response.query,
                    "query_type": response.query_type,
                    "results": serialized_results,
                    "total_results": response.total_results,
                    "response_time": response.response_time,
                    "metadata": response.metadata,
                    "ai_analysis": response.ai_analysis
                },
                message=f"Search completed successfully for '{request.query}'"
            )
            
        except Exception as e:
            logging.error(f"Search failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/device/intelligence", response_model=APIResponse)
    async def get_device_intelligence(
        request: DeviceIntelligenceRequest,
        user=Depends(get_current_user) if config.auth.enabled else None
    ):
        """Get comprehensive device intelligence"""
        try:
            intelligence = await explorer.get_device_intelligence(
                device_name=request.device_name,
                lookback_months=request.lookback_months,
                include_risk_assessment=request.include_risk_assessment
            )
            
            # Serialize DataFrames
            serialized_data = {}
            for endpoint, df in intelligence["data"].items():
                serialized_data[endpoint] = df.to_dict('records')
            
            intelligence["data"] = serialized_data
            
            return APIResponse(
                success=True,
                data=intelligence,
                message=f"Device intelligence generated for '{request.device_name}'"
            )
            
        except Exception as e:
            logging.error(f"Device intelligence failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/device/compare", response_model=APIResponse)
    async def compare_devices(
        request: DeviceComparisonRequest,
        user=Depends(get_current_user) if config.auth.enabled else None
    ):
        """Compare multiple devices"""
        try:
            comparison = await explorer.compare_devices(
                device_names=request.device_names,
                lookback_months=request.lookback_months
            )
            
            # Serialize nested DataFrames
            serialized_device_data = {}
            for device_name, device_info in comparison["device_data"].items():
                serialized_data = {}
                for endpoint, df in device_info["data"].items():
                    serialized_data[endpoint] = df.to_dict('records')
                
                serialized_device_data[device_name] = {
                    **device_info,
                    "data": serialized_data
                }
            
            comparison["device_data"] = serialized_device_data
            
            return APIResponse(
                success=True,
                data=comparison,
                message=f"Device comparison completed for {len(request.device_names)} devices"
            )
            
        except Exception as e:
            logging.error(f"Device comparison failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/trends", response_model=APIResponse)
    async def analyze_trends(
        request: TrendAnalysisRequest,
        user=Depends(get_current_user) if config.auth.enabled else None
    ):
        """Analyze trends over time"""
        try:
            trends = await explorer.get_trend_analysis(
                query=request.query,
                time_periods=request.time_periods
            )
            
            # Serialize trend data
            serialized_trend_data = {}
            for period, data in trends["trend_data"].items():
                serialized_data = {}
                for endpoint, df in data.items():
                    serialized_data[endpoint] = df.to_dict('records')
                serialized_trend_data[period] = serialized_data
            
            trends["trend_data"] = serialized_trend_data
            
            return APIResponse(
                success=True,
                data=trends,
                message=f"Trend analysis completed for '{request.query}'"
            )
            
        except Exception as e:
            logging.error(f"Trend analysis failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/manufacturer/{manufacturer_name}/intelligence", response_model=APIResponse)
    async def get_manufacturer_intelligence(
        manufacturer_name: str,
        lookback_months: int = Query(default=12, ge=1, le=60),
        user=Depends(get_current_user) if config.auth.enabled else None
    ):
        """Get manufacturer intelligence"""
        try:
            intelligence = await explorer.get_manufacturer_intelligence(
                manufacturer_name=manufacturer_name,
                lookback_months=lookback_months
            )
            
            # Serialize search response results
            serialized_results = {}
            for endpoint, df in intelligence["search_response"].results.items():
                serialized_results[endpoint] = df.to_dict('records')
            
            intelligence["search_response"].results = serialized_results
            
            return APIResponse(
                success=True,
                data=intelligence,
                message=f"Manufacturer intelligence generated for '{manufacturer_name}'"
            )
            
        except Exception as e:
            logging.error(f"Manufacturer intelligence failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/regulatory/insights", response_model=APIResponse)
    async def get_regulatory_insights(
        query: str = Query(..., description="Search query"),
        analysis_type: str = Query(default="summary", description="Analysis type"),
        user=Depends(get_current_user) if config.auth.enabled else None
    ):
        """Get regulatory insights"""
        try:
            insights = await explorer.get_regulatory_insights(
                query=query,
                analysis_type=analysis_type
            )
            
            # Serialize search response results
            serialized_results = {}
            for endpoint, df in insights["search_response"].results.items():
                serialized_results[endpoint] = df.to_dict('records')
            
            insights["search_response"].results = serialized_results
            
            return APIResponse(
                success=True,
                data=insights,
                message=f"Regulatory insights generated for '{query}'"
            )
            
        except Exception as e:
            logging.error(f"Regulatory insights failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/statistics", response_model=APIResponse)
    async def get_statistics(
        user=Depends(get_current_user) if config.auth.enabled else None
    ):
        """Get summary statistics"""
        try:
            stats = await explorer.get_summary_statistics()
            
            return APIResponse(
                success=True,
                data=stats,
                message="Statistics retrieved successfully"
            )
            
        except Exception as e:
            logging.error(f"Statistics retrieval failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Error handlers
    @app.exception_handler(404)
    async def not_found_handler(request, exc):
        return JSONResponse(
            status_code=404,
            content=APIResponse(
                success=False,
                error="Endpoint not found",
                message="The requested endpoint does not exist"
            ).dict()
        )
    
    @app.exception_handler(500)
    async def internal_error_handler(request, exc):
        return JSONResponse(
            status_code=500,
            content=APIResponse(
                success=False,
                error="Internal server error",
                message="An unexpected error occurred"
            ).dict()
        )
    
    return app


def run_api_server():
    """Run the API server with configuration validation"""
    try:
        # Ensure configuration is valid before starting server
        config = ensure_valid_config()
        
        print(f"Starting Enhanced FDA Explorer API server...")
        print(f"Host: {config.api.host}")
        print(f"Port: {config.api.port}")
        print(f"Debug mode: {config.api.debug}")
        print(f"Environment: {config.environment}")
        
        uvicorn.run(
            "enhanced_fda_explorer.api:create_app",
            host=config.api.host,
            port=config.api.port,
            reload=config.api.debug,
            factory=True,
            log_level="debug" if config.debug else "info"
        )
        
    except ValueError as e:
        print(f"Configuration validation failed: {e}")
        print("Please fix configuration issues before starting the server.")
        return 1
    except Exception as e:
        print(f"Failed to start server: {e}")
        return 1


if __name__ == "__main__":
    run_api_server()