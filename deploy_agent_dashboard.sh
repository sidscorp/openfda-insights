#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}Deploying FDA Multi-Agent Intelligence System...${NC}"

# Build the Next.js frontend
echo -e "${GREEN}Building Next.js frontend...${NC}"
cd frontend
npm install
npm run build

if [ $? -ne 0 ]; then
    echo -e "${RED}Build failed!${NC}"
    exit 1
fi

# Create deployment directory
DEPLOY_DIR="/var/www/portfolio.snambiar.com/fda"
echo -e "${GREEN}Creating deployment directory at $DEPLOY_DIR...${NC}"
sudo mkdir -p $DEPLOY_DIR

# Copy built files
echo -e "${GREEN}Copying built files...${NC}"
sudo cp -r out/* $DEPLOY_DIR/

# Set correct permissions
sudo chown -R www-data:www-data $DEPLOY_DIR
sudo chmod -R 755 $DEPLOY_DIR

# Create systemd service for the API
echo -e "${GREEN}Creating systemd service for multi-agent API...${NC}"
sudo tee /etc/systemd/system/fda-agent-api.service > /dev/null <<EOF
[Unit]
Description=FDA Multi-Agent API Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/root/portfolio/analytics-projects/openfda-insights
Environment="PATH=/usr/bin:/usr/local/bin"
Environment="PYTHONPATH=/root/portfolio/analytics-projects/openfda-insights"
ExecStart=/usr/bin/python3 -m src.enhanced_fda_explorer serve --host 127.0.0.1 --port 8001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create logs directory
sudo mkdir -p /var/log/fda-agent-api
sudo chown www-data:www-data /var/log/fda-agent-api

# Reload systemd and start service
echo -e "${GREEN}Starting API service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable fda-agent-api
sudo systemctl restart fda-agent-api

# Check service status
sleep 3
if sudo systemctl is-active --quiet fda-agent-api; then
    echo -e "${GREEN}API service started successfully!${NC}"
else
    echo -e "${RED}API service failed to start. Check logs with: sudo journalctl -u fda-agent-api${NC}"
    exit 1
fi

# Update nginx configuration
echo -e "${GREEN}Updating nginx configuration...${NC}"
NGINX_CONF="/etc/nginx/sites-available/portfolio.snambiar.com"

# Check if FDA location blocks already exist
if ! grep -q "location /fda" "$NGINX_CONF"; then
    echo -e "${BLUE}Adding FDA location blocks to nginx config...${NC}"
    # Insert the FDA configuration before the closing brace
    sudo sed -i '/^}$/i \    # FDA Multi-Agent Explorer\n    location /fda {\n        alias /var/www/portfolio.snambiar.com/fda;\n        try_files $uri $uri/ /fda/index.html;\n        \n        # Security headers\n        add_header X-Frame-Options "SAMEORIGIN" always;\n        add_header X-Content-Type-Options "nosniff" always;\n        add_header X-XSS-Protection "1; mode=block" always;\n        \n        # Cache static assets\n        location ~* \\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {\n            expires 30d;\n            add_header Cache-Control "public, immutable";\n        }\n    }\n    \n    location /fda/api {\n        proxy_pass http://127.0.0.1:8001/api;\n        proxy_http_version 1.1;\n        proxy_set_header Upgrade $http_upgrade;\n        proxy_set_header Connection '"'"'upgrade'"'"';\n        proxy_set_header Host $host;\n        proxy_cache_bypass $http_upgrade;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        proxy_set_header X-Forwarded-Proto $scheme;\n        \n        # Timeouts for long-running AI requests\n        proxy_connect_timeout 60s;\n        proxy_send_timeout 60s;\n        proxy_read_timeout 60s;\n        \n        # SSE/WebSocket support for agent streaming\n        proxy_buffering off;\n        proxy_cache off;\n        chunked_transfer_encoding off;\n    }' "$NGINX_CONF"
fi

# Test nginx configuration
echo -e "${GREEN}Testing nginx configuration...${NC}"
sudo nginx -t

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Reloading nginx...${NC}"
    sudo systemctl reload nginx
    echo -e "${GREEN}✅ Deployment complete!${NC}"
    echo ""
    echo -e "${BLUE}FDA Multi-Agent Intelligence System is now available at:${NC}"
    echo -e "${GREEN}https://portfolio.snambiar.com/fda${NC}"
    echo -e "${GREEN}Multi-Agent Dashboard: https://portfolio.snambiar.com/fda/agents${NC}"
    echo ""
    echo -e "${BLUE}API Status:${NC}"
    curl -s http://127.0.0.1:8001/api/health | jq '.'
else
    echo -e "${RED}Nginx configuration test failed!${NC}"
    exit 1
fi