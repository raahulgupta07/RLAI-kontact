#!/bin/bash
echo "Building KONTACT..."
docker compose build
echo "Starting KONTACT..."
docker compose up -d
echo "KONTACT is running at http://localhost:${PORT:-8000}"
