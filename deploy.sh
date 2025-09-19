#!/bin/bash

echo "🚀 Deploying FDA Explorer to portfolio.snambiar.com/fda..."

# Build frontend
echo "📦 Building Next.js frontend..."
cd frontend
npm run build

# Deploy frontend to nginx
echo "🌐 Deploying frontend to server..."
sudo mkdir -p /var/www/portfolio.snambiar.com/fda
sudo cp -r out/* /var/www/portfolio.snambiar.com/fda/

# Fix permissions
echo "🔧 Setting permissions..."
sudo chown -R www-data:www-data /var/www/portfolio.snambiar.com/fda/
sudo chmod -R 755 /var/www/portfolio.snambiar.com/fda/

# Start backend API if not running
echo "🔌 Checking backend API..."
if ! pgrep -f "uvicorn enhanced_fda_explorer.api:app" > /dev/null; then
    echo "Starting backend API..."
    cd ..
    nohup uvicorn enhanced_fda_explorer.api:app --host 127.0.0.1 --port 8000 > api.log 2>&1 &
    echo "Backend API started on port 8000"
else
    echo "Backend API already running"
fi

# Reload nginx
echo "🔄 Reloading nginx..."
sudo systemctl reload nginx

echo "✨ Deployment complete! Check https://portfolio.snambiar.com/fda"