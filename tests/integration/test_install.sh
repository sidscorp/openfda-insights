#!/bin/bash

echo "🚀 Enhanced FDA Explorer - Installation Test Script"
echo "=================================================="

# Check if we're in the right directory
if [ ! -f "setup.py" ]; then
    echo "❌ Error: setup.py not found. Please run from project root directory."
    exit 1
fi

echo "📦 Installing Enhanced FDA Explorer..."

# Install in development mode
pip install -e .

if [ $? -eq 0 ]; then
    echo "✅ Installation successful!"
else
    echo "❌ Installation failed!"
    exit 1
fi

echo ""
echo "🧪 Running setup test..."
python3 test_setup.py

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Ready for testing!"
    echo ""
    echo "Next steps:"
    echo "1. Set up your API keys in .env:"
    echo "   - FDA_API_KEY (optional for basic testing)"  
    echo "   - AI_API_KEY (required for AI features)"
    echo ""
    echo "2. Run basic tests:"
    echo "   python3 test_basic.py"
    echo ""
    echo "3. Test specific components:"
    echo "   python3 test_client.py"
    echo "   python3 test_api.py"
    echo "   python3 test_web.py"
else
    echo "❌ Setup test failed. Please check the errors above."
fi