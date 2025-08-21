#!/usr/bin/env python3
"""
Data Transformation Pipeline Runner
Executes all transformation scripts in the correct order to create the final integrated database.
"""

import sys
import importlib.util
from pathlib import Path
from loguru import logger
import glob

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

def run_transform_pipeline():
    """
    Run all transformation scripts to create the final integrated database.
    Scripts are executed in order based on their step numbers.
    """
    logger.info("Starting data transformation pipeline...")
    
    # Define the transform directory
    transform_dir = Path(__file__).parent.parent / "transfrom"
    
    if not transform_dir.exists():
        logger.error(f"Transform directory not found: {transform_dir}")
        return {
            'successful': 0,
            'failed': 1,
            'failed_details': ['Transform directory not found'],
            'scripts_run': []
        }
    
    # Find all transform scripts (excluding __init__.py)
    transform_scripts = sorted([
        f for f in transform_dir.glob("step_*.py")
        if f.name != "__init__.py"
    ])
    
    if not transform_scripts:
        logger.warning("No transformation scripts found")
        return {
            'successful': 0,
            'failed': 0,
            'failed_details': [],
            'scripts_run': []
        }
    
    logger.info(f"Found {len(transform_scripts)} transformation scripts:")
    for script in transform_scripts:
        logger.info(f"  - {script.name}")
    
    successful_transforms = 0
    failed_transforms = []
    scripts_run = []
    
    # Execute each transformation script
    for script_path in transform_scripts:
        script_name = script_path.stem
        scripts_run.append(script_name)
        
        try:
            logger.info(f"Running transformation: {script_name}")
            
            # Import the script module
            spec = importlib.util.spec_from_file_location(script_name, script_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load module spec for {script_name}")
                
            transform_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(transform_module)
            
            # Execute the main function
            if hasattr(transform_module, 'main'):
                result = transform_module.main()
                
                if result:
                    successful_transforms += 1
                    logger.info(f"✅ Successfully completed transformation: {script_name}")
                else:
                    failed_transforms.append(f"{script_name}: main() returned False")
                    logger.error(f"❌ Transformation failed: {script_name}")
            else:
                failed_transforms.append(f"{script_name}: No main() function found")
                logger.warning(f"⚠️  No main() function in {script_name}")
                
        except Exception as e:
            failed_transforms.append(f"{script_name}: {str(e)}")
            logger.error(f"❌ Error running transformation {script_name}: {e}")
    
    # Summary
    logger.info("=== TRANSFORMATION PIPELINE SUMMARY ===")
    logger.info(f"Total scripts: {len(transform_scripts)}")
    logger.info(f"Successful: {successful_transforms}")
    logger.info(f"Failed: {len(failed_transforms)}")
    
    if failed_transforms:
        logger.warning("Failed transformations:")
        for failure in failed_transforms:
            logger.warning(f"  - {failure}")
    
    if successful_transforms == len(transform_scripts):
        logger.info("🎉 All transformations completed successfully!")
    elif successful_transforms > 0:
        logger.warning(f"⚠️  Pipeline completed with {len(failed_transforms)} failures")
    else:
        logger.error("❌ All transformations failed")
    
    return {
        'successful': successful_transforms,
        'failed': len(failed_transforms),
        'failed_details': failed_transforms,
        'scripts_run': scripts_run,
        'total_scripts': len(transform_scripts)
    }

def main():
    """Main entry point when script is run directly."""
    logger.info("Data Transformation Pipeline Runner")
    logger.info("===================================")
    
    result = run_transform_pipeline()
    
    # Exit with appropriate code
    if result['failed'] == 0:
        logger.info("Pipeline completed successfully!")
        sys.exit(0)
    else:
        logger.error(f"Pipeline completed with {result['failed']} failures")
        sys.exit(1)

if __name__ == "__main__":
    main()