#!/bin/bash
set -e
cd frontend
npm install
mkdir -p public
curl -sL "https://raw.githubusercontent.com/Kytosyn/amazon-sg-price-tracker/master/data/products.json" -o public/products.json 2>/dev/null || echo '{"products":[],"lastUpdated":null,"exportedAt":null}' > public/products.json
npm run build
cp public/products.json dist/products.json 2>/dev/null || true
