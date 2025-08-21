#!/bin/bash

# Script to create a clean git repository without large files in history

echo "🧹 Creating clean repository backup..."

# Create backup directory
BACKUP_DIR="../madrid-open-data-clean"
ORIGINAL_DIR=$(pwd)

# Remove backup if it exists
rm -rf "$BACKUP_DIR"

# Copy current directory excluding git and large files
echo "📁 Copying project files..."
mkdir -p "$BACKUP_DIR"

# Copy everything except .git, databases, and large data files
rsync -av --progress \
  --exclude='.git' \
  --exclude='rampa/duckdb/databases/' \
  --exclude='rampa/data/*.json' \
  --exclude='rampa/data/*.geojson' \
  --exclude='*.log' \
  --exclude='__pycache__' \
  ./ "$BACKUP_DIR/"

cd "$BACKUP_DIR"

# Initialize new git repository
echo "🔧 Initializing new git repository..."
git init
git add .
git commit -m "Initial commit with clean project structure

- Excluded large database files and data files
- Updated .gitignore to prevent future large file commits
- Clean project structure for Madrid Open Data analysis"

echo "✅ Clean repository created at: $BACKUP_DIR"
echo ""
echo "To use this clean repository:"
echo "1. cd $BACKUP_DIR"
echo "2. git remote add origin https://github.com/mehrrero/madrid_open_data.git"
echo "3. git push -u origin main --force"
echo ""
echo "⚠️  This will overwrite the remote repository!"
echo "Make sure you have backups of any important data."

cd "$ORIGINAL_DIR"
