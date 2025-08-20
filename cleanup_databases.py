#!/usr/bin/env python3
"""
Database Cleanup Script
Removes duplicate databases created by inconsistent naming.
"""

import os
import sys
import glob
from pathlib import Path
from loguru import logger

# Add project root to path to import config
sys.path.append(str(Path(__file__).parent))
from rampa.config import config

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

def cleanup_duplicate_databases():
    """Remove duplicate database files created by inconsistent naming."""
    logger.info("Cleaning up duplicate database files...")
    
    # Use configuration for database directory
    db_dir = Path(config.db_config["base_dir"])
    
    if not db_dir.exists():
        logger.info("Database directory does not exist, nothing to clean up")
        return
    
    # Find all database files
    db_files = list(db_dir.glob("*.db"))
    
    logger.info(f"Found {len(db_files)} database files:")
    for db_file in db_files:
        size_mb = db_file.stat().st_size / (1024 * 1024)
        logger.info(f"  {db_file.name}: {size_mb:.2f} MB")
    
    # Identify duplicates to remove
    duplicates_to_remove = []
    
    # Look for .db.db files (double extension)
    double_ext_files = [f for f in db_files if f.name.endswith('.db.db')]
    duplicates_to_remove.extend(double_ext_files)
    
    # Look for specific duplicate patterns
    duplicate_patterns = [
        ('madrid_layers.db.db', 'madrid_layers.db'),
        ('madrid_osm.db.db', 'madrid_osm.db'),
        ('rampa.db', 'rampa'),  # Keep the one with .db extension
    ]
    
    for dup_name, keep_name in duplicate_patterns:
        dup_path = db_dir / dup_name
        keep_path = db_dir / keep_name
        
        if dup_path.exists() and keep_path.exists():
            duplicates_to_remove.append(dup_path)
            logger.info(f"Will remove duplicate: {dup_name} (keeping {keep_name})")
        elif dup_path.exists():
            # Rename to the correct name
            logger.info(f"Renaming {dup_name} to {keep_name}")
            dup_path.rename(keep_path)
    
    # Remove duplicates
    if duplicates_to_remove:
        logger.info(f"Removing {len(duplicates_to_remove)} duplicate files...")
        for dup_file in duplicates_to_remove:
            try:
                dup_file.unlink()
                logger.info(f"✓ Removed: {dup_file.name}")
            except Exception as e:
                logger.error(f"✗ Failed to remove {dup_file.name}: {e}")
    else:
        logger.info("No duplicates found to remove")
    
    # Final summary
    remaining_files = list(db_dir.glob("*.db"))
    logger.info(f"Final database files ({len(remaining_files)}):")
    for db_file in remaining_files:
        size_mb = db_file.stat().st_size / (1024 * 1024)
        logger.info(f"  {db_file.name}: {size_mb:.2f} MB")

def standardize_database_names():
    """Ensure all databases follow consistent naming convention."""
    logger.info("Standardizing database names...")
    
    db_dir = Path("rampa/duckdb/databases")
    
    if not db_dir.exists():
        return
    
    # Standard naming: all should end with .db
    renames = []
    
    for db_file in db_dir.iterdir():
        if db_file.is_file() and not db_file.name.startswith('.'):
            if not db_file.name.endswith('.db'):
                new_name = f"{db_file.name}.db"
                new_path = db_dir / new_name
                
                if not new_path.exists():
                    renames.append((db_file, new_path))
    
    if renames:
        logger.info(f"Renaming {len(renames)} files to standard naming:")
        for old_path, new_path in renames:
            try:
                old_path.rename(new_path)
                logger.info(f"✓ Renamed: {old_path.name} → {new_path.name}")
            except Exception as e:
                logger.error(f"✗ Failed to rename {old_path.name}: {e}")
    else:
        logger.info("All database names are already standardized")

def main():
    """Main cleanup function."""
    import sys
    
    logger.info("=== DATABASE CLEANUP ===")
    
    # Step 1: Remove duplicates
    cleanup_duplicate_databases()
    
    logger.info("")
    
    # Step 2: Standardize names
    standardize_database_names()
    
    logger.info("=== CLEANUP COMPLETE ===")

if __name__ == "__main__":
    main()
