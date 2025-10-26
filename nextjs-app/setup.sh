#!/bin/bash
set -e

echo "=================================="
echo "Nighttime Story Prep - Setup"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo -e "${RED}Error: Run this script from the nextjs-app directory${NC}"
    exit 1
fi

# Check Node.js version
NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 20 ]; then
    echo -e "${RED}Node.js version 20.9.0 or higher is required${NC}"
    echo "Current version: $(node -v)"
    echo "Please upgrade Node.js and try again"
    exit 1
fi

# Check for Supabase CLI
if ! command -v supabase &> /dev/null; then
    echo -e "${RED}Supabase CLI not found${NC}"
    echo "Install it with: npm install -g supabase"
    exit 1
fi

# Check for Docker
if ! docker info &> /dev/null; then
    echo -e "${RED}Docker is not running${NC}"
    echo "Please start Docker Desktop and try again"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"
echo ""

# Check if Supabase is already initialized
if [ ! -d ".supabase" ]; then
    echo -e "${YELLOW}Initializing Supabase...${NC}"
    supabase init
    echo ""
fi

# Start Supabase
echo -e "${YELLOW}Starting Supabase (this may take a minute)...${NC}"
supabase start

# Get the credentials
echo ""
echo -e "${GREEN}✅ Supabase started successfully!${NC}"
echo ""
echo "Copy these credentials to your .env.local file:"
echo ""
supabase status | grep -E "API URL|anon key|service_role key"
echo ""

# Check if .env.local exists
if [ ! -f ".env.local" ]; then
    echo -e "${YELLOW}Creating .env.local from template...${NC}"
    if [ -f "env.example" ]; then
        cp env.example .env.local
        echo -e "${GREEN}✅ Created .env.local${NC}"
        echo -e "${YELLOW}⚠️  You need to update .env.local with the credentials above${NC}"
    else
        echo -e "${RED}env.example not found${NC}"
    fi
else
    echo -e "${GREEN}.env.local already exists${NC}"
fi

echo ""
echo -e "${YELLOW}Applying database migrations...${NC}"
supabase db reset

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Update .env.local with the credentials shown above"
echo "  2. Run: npm run dev"
echo "  3. Test: ../scripts/test/test-health.sh"
echo ""
echo "See SETUP_COMPLETE.md for detailed instructions"

