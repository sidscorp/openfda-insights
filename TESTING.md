# 🧪 Testing Guide for Enhanced FDA Explorer

This guide provides multiple ways to test the Enhanced FDA Explorer, from basic functionality to full integration testing.

## 🚀 Quick Start Testing

### 1. **One-Command Test Suite**
```bash
# Run complete test suite
python3 run_all_tests.py
```

### 2. **Manual Step-by-Step Testing**

#### Install and Basic Setup
```bash
# 1. Install the package
pip install -e .

# 2. Run basic functionality test
python3 test_basic.py

# 3. Test CLI
python3 test_cli.py

# 4. Test web interface
python3 test_web.py
```

#### Test with Real API Calls
```bash
# 1. Copy environment template
cp .env.example .env

# 2. Edit .env and add your API keys
nano .env

# 3. Run API integration tests
python3 test_with_api.py
```

## 📋 Test Categories

### ✅ **Basic Tests** (No API keys needed)
- **Setup Test**: `python3 test_setup.py`
- **Basic Functionality**: `python3 test_basic.py`
- **CLI Interface**: `python3 test_cli.py`
- **Web Interface**: `python3 test_web.py`

### 🔑 **API Integration Tests** (Requires API keys)
- **Full Integration**: `python3 test_with_api.py`

### 🌐 **Manual Interface Tests**
- **Web UI**: `python3 test_web_manual.py`
- **CLI Commands**: See CLI section below

## 💻 CLI Testing

### Basic CLI Commands
```bash
# Help
fda-explorer --help

# Search (basic)
fda-explorer search "pacemaker" --type device --limit 10

# Device intelligence
fda-explorer device "insulin pump" --lookback 6

# Compare devices
fda-explorer compare "pacemaker" "defibrillator"

# Get statistics
fda-explorer stats

# Start web interface
fda-explorer web

# Start API server
fda-explorer serve
```

### Test CLI Without API Keys
```bash
# These work without API keys
fda-explorer --help
fda-explorer search --help
fda-explorer stats
```

## 🌐 Web Interface Testing

### Start Web Interface
```bash
# Method 1: Using CLI
fda-explorer web

# Method 2: Direct Streamlit
streamlit run src/enhanced_fda_explorer/web.py

# Method 3: Manual test script
python3 test_web_manual.py
```

### Test Web Features
1. **Search Tab**: Try searching for "pacemaker"
2. **Device Intelligence**: Analyze "insulin pump"
3. **Trends**: Analyze trends for "cardiac device"
4. **Advanced**: Compare multiple devices

## 🔧 API Server Testing

### Start API Server
```bash
# Start server
fda-explorer serve --host 0.0.0.0 --port 8000

# In another terminal, test endpoints
curl http://localhost:8000/health
curl http://localhost:8000/
```

### Test API Endpoints
```bash
# Health check
curl http://localhost:8000/health

# Search endpoint
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "pacemaker",
    "query_type": "device",
    "limit": 5,
    "include_ai_analysis": false
  }'

# API documentation
# Open: http://localhost:8000/docs
```

## 🐳 Docker Testing

### Build and Test Container
```bash
# Build image
docker build -t enhanced-fda-explorer .

# Run container
docker run -p 8000:8000 -p 8501:8501 \
  -e FDA_API_KEY=your_key \
  enhanced-fda-explorer

# Test with docker-compose
docker-compose up
```

## 🔍 Troubleshooting Tests

### Common Issues and Solutions

#### **Import Errors**
```bash
# Install missing packages
pip install -e .

# Or install specific packages
pip install pydantic fastapi streamlit plotly
```

#### **Module Not Found**
```bash
# Make sure you're in the project root
ls setup.py  # Should exist

# Install in development mode
pip install -e .
```

#### **API Key Issues**
```bash
# Check .env file
cat .env

# Test without AI features first
python3 test_basic.py
```

#### **Permission Issues**
```bash
# Make scripts executable
chmod +x *.py
chmod +x *.sh
```

#### **Network/Timeout Issues**
- Check internet connection
- Try reducing test limits
- Test with simpler queries first

## 📊 Test Results Interpretation

### ✅ **Success Indicators**
- All basic tests pass
- CLI commands work
- Web interface loads
- API endpoints respond

### ⚠️ **Partial Success**
- Basic tests pass but API tests fail → Check API keys
- CLI works but web fails → Check Streamlit installation
- Some features work → Normal, depends on API keys

### ❌ **Failure Indicators**
- Import errors → Installation issue
- Module not found → Path/installation issue
- All tests fail → Major configuration issue

## 🎯 Testing Checklist

### Before Release Testing
- [ ] All basic tests pass
- [ ] CLI commands work
- [ ] Web interface loads and functions
- [ ] API server starts and responds
- [ ] Docker build succeeds
- [ ] Documentation is accurate

### Performance Testing
- [ ] Search completes in <10 seconds
- [ ] Web interface loads quickly
- [ ] API responds in <5 seconds
- [ ] Memory usage is reasonable

### Integration Testing
- [ ] FDA API integration works
- [ ] AI analysis functions (with API key)
- [ ] Database operations work
- [ ] Caching functions properly

## 🆘 Getting Help

### If Tests Fail
1. **Check Prerequisites**: Python 3.8+, internet connection
2. **Check Installation**: `pip install -e .`
3. **Check Configuration**: API keys in .env
4. **Check Logs**: Look for error messages
5. **Try Minimal Test**: `python3 test_setup.py`

### Support Resources
- **GitHub Issues**: Report bugs and get help
- **Documentation**: Check README.md for setup
- **API Documentation**: http://localhost:8000/docs (when server running)

### Test Environment Requirements
- **Python**: 3.8 or higher
- **Memory**: 2GB+ recommended
- **Network**: Internet connection for FDA API
- **API Keys**: OpenAI/OpenRouter key for AI features (optional for basic testing)

---

**Happy Testing! 🎉**

The Enhanced FDA Explorer is designed to work even without API keys for basic functionality. Start with the basic tests and gradually add API keys to unlock more features.