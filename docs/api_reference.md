# REST API Reference

Complete REST API documentation for Enhanced FDA Explorer.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

Currently, no authentication is required for the API. This may change in future versions.

```http
GET /api/v1/health
Content-Type: application/json
```

## Response Format

All API responses follow this standard format:

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "total": 100,
    "limit": 10,
    "skip": 0,
    "took": 150
  },
  "errors": []
}
```

### Error Response

```json
{
  "success": false,
  "data": null,
  "meta": {},
  "errors": [
    {
      "code": "INVALID_QUERY",
      "message": "Search query is required",
      "field": "query"
    }
  ]
}
```

## Core Endpoints

### Search FDA Data

Search across FDA databases with optional AI analysis.

```http
POST /api/v1/search
Content-Type: application/json
```

**Request Body:**
```json
{
  "query": "pacemaker",
  "query_type": "device",
  "limit": 100,
  "skip": 0,
  "include_ai_analysis": true,
  "ai_model": "gpt-4",
  "date_from": "2023-01-01",
  "date_to": "2023-12-31",
  "fields": ["device_name", "manufacturer", "date_received"],
  "filters": {
    "manufacturer": "Medtronic",
    "state": "CA",
    "country": "US"
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "device_name": "Pacemaker Model X",
        "manufacturer": "Medtronic",
        "date_received": "2023-06-15",
        "event_type": "Malfunction",
        "patient_outcome": "Required Intervention"
      }
    ],
    "ai_analysis": {
      "summary": "Analysis of pacemaker events shows...",
      "risk_score": 7.2,
      "trends": ["Increasing malfunction reports", "Geographic clustering"]
    }
  },
  "meta": {
    "total": 1247,
    "limit": 100,
    "skip": 0,
    "took": 245
  }
}
```

### Device Intelligence

Get comprehensive device analysis and intelligence.

```http
POST /api/v1/device/intelligence
Content-Type: application/json
```

**Request Body:**
```json
{
  "device_name": "insulin pump",
  "lookback_months": 12,
  "include_risk_assessment": true,
  "include_trends": true,
  "include_events": true,
  "include_recalls": true,
  "include_clearances": true,
  "manufacturer": "Medtronic"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "device_info": {
      "name": "insulin pump",
      "category": "Endocrinology",
      "regulation_number": "21CFR862.1570",
      "device_class": "II"
    },
    "risk_assessment": {
      "overall_risk_score": 6.8,
      "risk_factors": [
        "Software malfunctions",
        "Battery failures",
        "Infusion set occlusions"
      ],
      "risk_trends": "Stable over past 12 months"
    },
    "statistics": {
      "total_events": 2847,
      "total_recalls": 12,
      "total_clearances": 156,
      "manufacturers": 8
    },
    "trends": {
      "events_trend": "Increasing",
      "recall_trend": "Stable",
      "approval_trend": "Increasing"
    },
    "top_manufacturers": [
      {"name": "Medtronic", "market_share": 45.2},
      {"name": "Insulet", "market_share": 23.7},
      {"name": "Tandem", "market_share": 18.9}
    ]
  }
}
```

### Device Comparison

Compare multiple medical devices side-by-side.

```http
POST /api/v1/device/compare
Content-Type: application/json
```

**Request Body:**
```json
{
  "device_names": ["pacemaker", "defibrillator", "cardiac monitor"],
  "lookback_months": 12,
  "metrics": ["events", "recalls", "approvals"],
  "include_ai_insights": true
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "comparison": {
      "devices": [
        {
          "name": "pacemaker",
          "events": 3421,
          "recalls": 8,
          "approvals": 67,
          "risk_score": 6.2
        },
        {
          "name": "defibrillator", 
          "events": 1843,
          "recalls": 12,
          "approvals": 34,
          "risk_score": 7.8
        }
      ]
    },
    "ai_insights": {
      "summary": "Comparative analysis shows...",
      "key_differences": [
        "Defibrillators have higher risk scores due to complexity",
        "Pacemakers show more consistent approval patterns"
      ],
      "recommendations": "Consider device complexity when evaluating risks"
    }
  }
}
```

### Trend Analysis

Analyze trends across multiple time periods.

```http
POST /api/v1/trends
Content-Type: application/json
```

**Request Body:**
```json
{
  "query": "surgical robot",
  "periods": ["6months", "1year", "2years"],
  "query_type": "device",
  "metrics": ["events", "recalls", "approvals"],
  "include_ai_analysis": true,
  "manufacturer": "Intuitive Surgical"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "trends": {
      "6months": {
        "events": 156,
        "recalls": 2,
        "approvals": 8
      },
      "1year": {
        "events": 298,
        "recalls": 3,
        "approvals": 15
      },
      "2years": {
        "events": 542,
        "recalls": 7,
        "approvals": 28
      }
    },
    "trend_analysis": {
      "events_trend": "Increasing",
      "recall_trend": "Stable",
      "approval_trend": "Increasing"
    },
    "ai_analysis": {
      "summary": "Surgical robot adoption is increasing...",
      "patterns": ["Seasonal variations in events", "Steady approval pipeline"],
      "predictions": "Continued growth expected"
    }
  }
}
```

### Manufacturer Intelligence

Get comprehensive manufacturer analysis.

```http
GET /api/v1/manufacturer/{manufacturer_name}/intelligence
```

**Parameters:**
- `manufacturer_name`: URL-encoded manufacturer name
- `lookback_months`: Number of months to analyze (default: 12)
- `include_devices`: Include device portfolio (default: true)
- `include_risk_profile`: Include risk assessment (default: false)

**Response:**
```json
{
  "success": true,
  "data": {
    "manufacturer": {
      "name": "Medtronic",
      "headquarters": "Minneapolis, MN",
      "founded": 1949,
      "market_cap": "$120B"
    },
    "device_portfolio": [
      {
        "name": "pacemaker",
        "category": "Cardiovascular",
        "market_share": 35.2
      }
    ],
    "performance_metrics": {
      "total_devices": 1247,
      "total_events": 8932,
      "total_recalls": 45,
      "total_approvals": 234
    },
    "risk_profile": {
      "overall_risk_score": 6.5,
      "risk_categories": {
        "product_quality": 6.2,
        "regulatory_compliance": 7.1,
        "market_performance": 8.3
      }
    }
  }
}
```

### Regulatory Insights

Get regulatory pathway and approval insights.

```http
GET /api/v1/regulatory/insights
```

**Query Parameters:**
- `device`: Focus on specific device
- `manufacturer`: Focus on specific manufacturer
- `pathway`: Regulatory pathway (510k, pma, de_novo)
- `timeframe`: Analysis timeframe (1year, 2years, 5years)
- `include_trends`: Include trend analysis
- `include_ai_insights`: Include AI insights

**Response:**
```json
{
  "success": true,
  "data": {
    "regulatory_landscape": {
      "total_submissions": 12847,
      "approval_rate": 87.3,
      "average_review_time": 156
    },
    "pathway_analysis": {
      "510k": {
        "submissions": 9234,
        "approval_rate": 92.1,
        "avg_review_days": 124
      },
      "pma": {
        "submissions": 2156,
        "approval_rate": 78.4,
        "avg_review_days": 289
      }
    },
    "trends": {
      "submission_trend": "Increasing",
      "approval_rate_trend": "Stable",
      "review_time_trend": "Decreasing"
    }
  }
}
```

## Utility Endpoints

### Health Check

Check API health and status.

```http
GET /api/v1/health
```

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "version": "1.0.0",
    "uptime": 3600,
    "services": {
      "database": "connected",
      "cache": "connected",
      "openfda_api": "connected",
      "ai_service": "connected"
    }
  }
}
```

### API Information

Get API version and capabilities.

```http
GET /api/v1/info
```

**Response:**
```json
{
  "success": true,
  "data": {
    "name": "Enhanced FDA Explorer API",
    "version": "1.0.0",
    "description": "REST API for FDA medical device data exploration",
    "documentation": "https://docs.enhanced-fda-explorer.com",
    "rate_limits": {
      "requests_per_minute": 60,
      "requests_per_hour": 1000
    },
    "supported_databases": [
      "device_events",
      "device_recalls", 
      "device_510k",
      "device_pma",
      "device_classification",
      "device_udi"
    ]
  }
}
```

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_QUERY` | 400 | Invalid or missing query parameter |
| `INVALID_TYPE` | 400 | Invalid database type specified |
| `INVALID_DATE` | 400 | Invalid date format |
| `RATE_LIMITED` | 429 | Rate limit exceeded |
| `API_ERROR` | 500 | External API error |
| `TIMEOUT` | 504 | Request timeout |
| `UNAUTHORIZED` | 401 | Authentication required |
| `FORBIDDEN` | 403 | Access denied |

## Rate Limits

- **60 requests per minute** per IP address
- **1000 requests per hour** per IP address
- **10,000 requests per day** per IP address

Rate limit headers are included in all responses:
```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1640995200
```

## Webhooks

Subscribe to real-time updates (premium feature):

```http
POST /api/v1/webhooks
Content-Type: application/json
```

**Request Body:**
```json
{
  "url": "https://your-app.com/webhook",
  "events": ["new_recall", "device_alert"],
  "filters": {
    "device_types": ["pacemaker", "defibrillator"],
    "manufacturers": ["Medtronic"]
  }
}
```

## SDKs and Libraries

- **Python**: `pip install enhanced-fda-explorer`
- **Node.js**: `npm install enhanced-fda-explorer-js`
- **R**: `install.packages("enhancedfda")`

## OpenAPI Specification

The complete OpenAPI 3.0 specification is available at:
```
GET /api/v1/openapi.json
```

## Interactive Documentation

Explore the API interactively using Swagger UI:
```
http://localhost:8000/docs
```

Or ReDoc:
```
http://localhost:8000/redoc
```