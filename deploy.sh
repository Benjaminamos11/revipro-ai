#!/bin/bash
# Revipro Deployment Script

set -e

echo "🚀 Revipro Deployment Script"
echo "================================"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if flyctl is installed
if ! command -v fly &> /dev/null; then
    echo -e "${RED}❌ Fly CLI nicht gefunden!${NC}"
    echo "Installieren mit: brew install flyctl"
    exit 1
fi

echo -e "${BLUE}Wählen Sie eine Option:${NC}"
echo "1) Backend deployen"
echo "2) Frontend deployen"
echo "3) Beide deployen"
echo "4) Secrets setzen"
echo "5) Logs anzeigen"
read -p "Auswahl (1-5): " choice

case $choice in
    1)
        echo -e "${GREEN}📦 Backend wird deployed...${NC}"
        cd backend
        fly deploy
        echo -e "${GREEN}✅ Backend deployed!${NC}"
        echo "URL: https://revipro-backend.fly.dev"
        ;;
    2)
        echo -e "${GREEN}🎨 Frontend wird deployed...${NC}"
        cd frontend
        fly deploy
        echo -e "${GREEN}✅ Frontend deployed!${NC}"
        echo "URL: https://revipro-frontend.fly.dev"
        ;;
    3)
        echo -e "${GREEN}📦 Backend wird deployed...${NC}"
        cd backend
        fly deploy
        cd ..
        
        echo -e "${GREEN}🎨 Frontend wird deployed...${NC}"
        cd frontend
        fly deploy
        cd ..
        
        echo -e "${GREEN}✅ Beide Apps deployed!${NC}"
        echo "Backend: https://revipro-backend.fly.dev"
        echo "Frontend: https://revipro-frontend.fly.dev"
        ;;
    4)
        echo -e "${BLUE}🔐 Secrets setzen${NC}"
        echo ""
        echo "Backend Secrets:"
        cd backend
        echo "ANTHROPIC_API_KEY eingeben:"
        read -p "> " anthropic_key
        if [ ! -z "$anthropic_key" ]; then
            fly secrets set ANTHROPIC_API_KEY=$anthropic_key
        fi
        
        echo "SUPABASE_URL setzen? (j/n)"
        read -p "> " set_supabase_url
        if [ "$set_supabase_url" = "j" ]; then
            fly secrets set SUPABASE_URL=https://poeulzxkjcxeszfcsiks.supabase.co
        fi
        
        echo "SUPABASE_KEY (Service Role) eingeben:"
        read -p "> " supabase_key
        if [ ! -z "$supabase_key" ]; then
            fly secrets set SUPABASE_KEY=$supabase_key
        fi
        
        cd ..
        
        echo ""
        echo "Frontend Secrets:"
        cd frontend
        echo "Backend URL eingeben (z.B. https://revipro-backend.fly.dev):"
        read -p "> " backend_url
        if [ ! -z "$backend_url" ]; then
            fly secrets set NEXT_PUBLIC_API_URL=$backend_url
        fi
        
        echo -e "${GREEN}✅ Secrets gesetzt!${NC}"
        ;;
    5)
        echo -e "${BLUE}📋 Welche Logs?${NC}"
        echo "1) Backend"
        echo "2) Frontend"
        read -p "Auswahl (1-2): " log_choice
        
        if [ "$log_choice" = "1" ]; then
            fly logs -a revipro-backend
        else
            fly logs -a revipro-frontend
        fi
        ;;
    *)
        echo -e "${RED}Ungültige Auswahl${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}🎉 Fertig!${NC}"
