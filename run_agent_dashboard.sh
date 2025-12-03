#!/bin/bash

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Starting FDA Explorer...${NC}"

# Start the FastAPI backend
echo -e "${GREEN}Starting API server on port 8001...${NC}"
python3 -m src.enhanced_fda_explorer serve --port 8001 &
API_PID=$!

sleep 3

# Start the Next.js frontend
echo -e "${GREEN}Starting Next.js frontend on port 3000...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!

echo -e "${BLUE}Services started!${NC}"
echo "API Server PID: $API_PID (http://localhost:8001)"
echo "Frontend PID: $FRONTEND_PID (http://localhost:3000)"
echo ""
echo -e "${GREEN}Press Ctrl+C to stop all services...${NC}"

trap "echo -e '\n${BLUE}Stopping services...${NC}'; kill $API_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait
