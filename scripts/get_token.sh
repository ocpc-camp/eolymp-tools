#!/bin/bash
# Get Eolymp API token interactively

echo "Eolymp Token Request"
echo "===================="
echo ""

read -p "Username (Eolymp account): " username
read -sp "Password: " password
echo ""

echo "Requesting token..."
response=$(curl -s -d "grant_type=password&username=$username&password=$password" https://api.eolymp.com/oauth/token)

token=$(echo "$response" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -z "$token" ]; then
    echo "❌ Failed to get token. Response:"
    echo "$response"
    exit 1
fi

echo ""
echo "✓ Token received!"
echo ""
echo "Export the token with:"
echo ""
echo "export EOLYMP_TOKEN='$token'"
echo ""
