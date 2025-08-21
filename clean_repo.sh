#!/bin/bash
# Script to create a clean repository without large files in history

echo "🧹 Creating a clean repository without large files..."

# Create a temporary directory for the clean repo
TEMP_DIR="../madrid-open-data-clean"
CURRENT_DIR=$(pwd)

# Remove existing temp directory if it exists
rm -rf "$TEMP_DIR"

# Create new directory and initialize git
mkdir "$TEMP_DIR"
cd "$TEMP_DIR"
git init
git branch -m main graph_analysis

echo "📁 Copying files (excluding large data files and databases)..."

# Copy all files except the ones we want to exclude
rsync -av --progress "$CURRENT_DIR/" . \
    --exclude='.git' \
    --exclude='*.db' \
    --exclude='rampa/duckdb/databases/' \
    --exclude='rampa/data/*.json' \
    --exclude='rampa/data/*.geojson' \
    --exclude='*.log' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc'

# Add and commit all files
git add .
git commit -m "Initial commit without large files

- Excluded database files (*.db)
- Excluded large JSON/GeoJSON data files  
- Excluded virtual environment and cache files
- Added comprehensive .gitignore"

echo "✅ Clean repository created in $TEMP_DIR"
echo ""
echo "🔧 Next steps:"
echo "1. cd $TEMP_DIR"
echo "2. git remote add origin https://github.com/mehrrero/madrid_open_data.git"
echo "3. git push --force-with-lease origin graph_analysis"
echo ""
echo "📝 Note: This will overwrite the remote branch history."
echo "   Make sure you don't need anything from the current remote state."
