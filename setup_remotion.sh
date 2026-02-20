#!/bin/bash

echo "Setting up Remotion service for Flowcut..."

# Navigate to project root
cd /home/lol/project/core

# Create remotion-service directory
mkdir -p remotion-service
cd remotion-service

# Initialize if not already done
if [ ! -f "package.json" ]; then
    echo "Initializing Node.js project..."
    npm init -y
fi

# Install dependencies
echo "Installing Remotion and dependencies..."
npm install remotion @remotion/cli @remotion/bundler @remotion/renderer
npm install react react-dom
npm install express
npm install --save-dev @types/react @types/react-dom @types/express @types/node typescript ts-node

# Create directory structure
echo "Creating directory structure..."
mkdir -p src/templates/ProductLaunch
mkdir -p src/api
mkdir -p output

echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Start the service: npm run serve"
echo "2. Test in Flowcut: 'Create a product launch video for facebook/react'"
