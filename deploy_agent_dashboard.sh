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
rm -rf out
npm install
npm run build

if [ $? -ne 0 ]; then
    echo -e "${RED}Build failed!${NC}"
    exit 1
fi

# Create deployment directory
DEPLOY_DIR="/var/www/openfda-agent.snambiar.com"
echo -e "${GREEN}Creating deployment directory at $DEPLOY_DIR...${NC}"
sudo mkdir -p $DEPLOY_DIR

# Clean existing files to prevent stale directory conflicts
echo -e "${GREEN}Cleaning deployment directory...${NC}"
sudo rm -rf $DEPLOY_DIR/*

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
User=root
WorkingDirectory=/root/projects/analytics-projects/openfda-insights
EnvironmentFile=/root/projects/analytics-projects/openfda-insights/.env
Environment="PATH=/usr/bin:/usr/local/bin"
Environment="PYTHONPATH=/root/projects/analytics-projects/openfda-insights"
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

# Create nginx configuration for openfda-agent.snambiar.com
echo -e "${GREEN}Creating nginx configuration...${NC}"
NGINX_CONF="/etc/nginx/sites-available/openfda-agent.snambiar.com"

sudo tee "$NGINX_CONF" > /dev/null <<'EOF'
server {
    listen 80;
    server_name openfda-agent.snambiar.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name openfda-agent.snambiar.com;
    
    ssl_certificate /etc/letsencrypt/live/openfda-agent.snambiar.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/openfda-agent.snambiar.com/privkey.pem;
    
    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    root /var/www/openfda-agent.snambiar.com;
    index index.html;
    
    # Frontend static files
    location / {
        try_files $uri $uri/ /index.html;
        
        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        
        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 30d;
            add_header Cache-Control "public, immutable";
        }
    }
    
    # API proxy to backend
    location /api {
        proxy_pass http://127.0.0.1:8001/api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts for long-running AI requests
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # SSE/WebSocket support for agent streaming
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
    }
}
EOF

# Enable the site
sudo ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/

# Test nginx configuration
echo -e "${GREEN}Testing nginx configuration...${NC}"
sudo nginx -t

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Reloading nginx...${NC}"
    sudo systemctl reload nginx
    echo -e "${GREEN}✅ Deployment complete!${NC}"
    echo ""
    echo -e "${BLUE}FDA Multi-Agent Intelligence System is now available at:${NC}"
    echo -e "${GREEN}https://openfda-agent.snambiar.com${NC}"
    echo -e "${GREEN}Multi-Agent Dashboard: https://openfda-agent.snambiar.com/agents${NC}"
    echo ""
    echo -e "${BLUE}API Status:${NC}"
    curl -s http://127.0.0.1:8001/api/health | jq '.'
else
    echo -e "${RED}Nginx configuration test failed!${NC}"
    exit 1
fi