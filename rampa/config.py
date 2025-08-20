#!/usr/bin/env python3
"""
Central Configuration for Madrid Open Data Project
<<<<<<< HEAD
"""

from pathlib import Path
=======
Defines all database paths, settings, and constants in one place.
"""

import os
from pathlib import Path
from typing import Dict, Any
>>>>>>> 433b687 (Refactor geospatial processing and demographics scripts; improve error handling and logging)

try:
    import tomllib  # Python 3.11+
except ImportError:
<<<<<<< HEAD
    import tomli as tomllib  # Fallback for older Python versions

class Config:
    """Simple configuration class."""
    
    def __init__(self):
        # Auto-detect project root
        self.project_root = Path(__file__).parent.parent
        
        # Load from TOML file
        config_file = self.project_root / "config.toml"
        if config_file.exists():
            with open(config_file, 'rb') as f:
                data = tomllib.load(f)
            
            # Database paths
            base_dir = self.project_root / data.get('database', {}).get('base_dir', 'rampa/duckdb/databases')
            db_names = data.get('database', {}).get('names', {})
            
            self.databases = {
                name: str(base_dir / db_name)
                for name, db_name in db_names.items()
            }
            
            # Other configs
            self.arcgis = data.get('arcgis', {})
            self.transform = data.get('transform', {})
            
        else:
            # Fallback defaults
            base_dir = self.project_root / "rampa/duckdb/databases"
            self.databases = {
                "arcgis": str(base_dir / "madrid_layers"),
                "final": str(base_dir / "rampa"),
                "test": str(base_dir / "test")
            }
            self.arcgis = {"enabled": True, "urls_file": "rampa/data/urls.json"}
            self.transform = {"transform_dir": "rampa/duckdb/transfrom"}
    
    def get_db_path(self, db_name: str) -> str:
        """Get database path."""
        return self.databases.get(db_name, "")
    
    def ensure_directories(self):
        """Create database directory if needed."""
        for db_path in self.databases.values():
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

# Global config instance
config = Config()

# Convenience function
def get_db_path(db_name: str) -> str:
    """Get database path."""
    return config.get_db_path(db_name)

if __name__ == "__main__":
    print("=== MADRID OPEN DATA CONFIGURATION ===")
    print(f"Project root: {config.project_root}")
    print("Database paths:")
    for name, path in config.databases.items():
        print(f"  {name}: {path}")
    print(f"ArcGIS enabled: {config.arcgis.get('enabled', False)}")
=======
    try:
        import tomli as tomllib  # Fallback for older Python versions
    except ImportError:
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "tomli"])
        import tomli as tomllib

try:
    import tomli_w  # For writing TOML files
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "tomli-w"])
    import tomli_w

class MadridDataConfig:
    """Central configuration class for the Madrid Open Data project."""
    
    def __init__(self, project_root: str = None, config_file: str = None):
        """
        Initialize configuration.
        
        Args:
            project_root: Path to project root directory
            config_file: Path to TOML config file
        """
        if project_root is None:
            # Auto-detect project root (go up one level from rampa directory)
            self.project_root = Path(__file__).parent.parent
        else:
            self.project_root = Path(project_root)
        
        # Load from TOML file if provided, otherwise use defaults
        if config_file and Path(config_file).exists():
            self._load_from_toml(config_file)
        else:
            # Default configuration
            self._setup_default_config()
    
    def _setup_default_config(self):
        """Setup default configuration."""
        # Database configuration
        self.db_config = self._setup_database_config()
        
        # OSM configuration
        self.osm_config = self._setup_osm_config()
        
        # `GIS configuration
        self.arcgis_config = self._setup_arcgis_config()
        
        # Transformation configuration
        self.transform_config = self._setup_transform_config()
        
        # Logging configuration
        self.logging_config = self._setup_logging_config()
    
    def _load_from_toml(self, config_file: str):
        """Load configuration from TOML file."""
        with open(config_file, 'rb') as f:
            config_data = tomllib.load(f)
        
        # Convert TOML structure to internal format
        self.db_config = self._convert_db_config(config_data.get('database', {}))
        self.osm_config = self._convert_osm_config(config_data.get('osm', {}))
        self.arcgis_config = config_data.get('arcgis', {})
        self.transform_config = config_data.get('transform', {})
        self.logging_config = config_data.get('logging', {})
    
    def _convert_db_config(self, db_data: Dict) -> Dict[str, Any]:
        """Convert TOML database config to internal format."""
        base_dir = self.project_root / db_data.get('base_dir', 'rampa/duckdb/databases')
        db_names = db_data.get('names', {})
        
        return {
            "base_dir": base_dir,
            "databases": {
                name: str(base_dir / db_name)
                for name, db_name in db_names.items()
            },
            "database_files": {
                name: str(base_dir / f"{db_name}.db")
                for name, db_name in db_names.items()
            },
            "creation_order": db_data.get('creation_order', ["arcgis", "osm", "final"])
        }
    
    def _convert_osm_config(self, osm_data: Dict) -> Dict[str, Any]:
        """Convert TOML OSM config to internal format."""
        return {
            "madrid_bbox": tuple(osm_data.get('madrid_bbox', (40.3119, -3.8633, 40.564, -3.5179))),
            "overpass_url": osm_data.get('overpass_url', "http://overpass-api.de/api/interpreter"),
            "timeout": osm_data.get('timeout', 600),
            "layers": osm_data.get('layers', {}),
            "special_collections": osm_data.get('special_collections', {})
        }
    
    def _setup_database_config(self) -> Dict[str, Any]:
        """Setup database configuration."""
        db_base_dir = self.project_root / "rampa" / "duckdb" / "databases"
        
        return {
            # Base directory for all databases
            "base_dir": str(db_base_dir),
            
            # Individual database paths (without .db extension - connection.py will add it)
            "databases": {
                "arcgis": str(db_base_dir / "madrid_layers"),
                "osm": str(db_base_dir / "madrid_osm"), 
                "final": str(db_base_dir / "rampa"),
                "test": str(db_base_dir / "test")
            },
            
            # Full paths with .db extension (for direct file operations)
            "database_files": {
                "arcgis": str(db_base_dir / "madrid_layers.db"),
                "osm": str(db_base_dir / "madrid_osm.db"),
                "final": str(db_base_dir / "rampa.db"),
                "test": str(db_base_dir / "test.db")
            },
            
            # Database creation order
            "creation_order": ["arcgis", "osm", "final"]
        }
    
    def _setup_osm_config(self) -> Dict[str, Any]:
        """Setup OSM data configuration."""
        return {
            # Madrid bounding box (south, west, north, east)
            "madrid_bbox": (40.3119, -3.8633, 40.5640, -3.5179),
            
            # OSM API settings
            "overpass_url": "http://overpass-api.de/api/interpreter",
            "timeout": 600,
            
            # OSM data layers to collect
            "layers": {
                'amenities': {
                    'feature_types': ['amenity'],
                    'query_type': 'accessible_pois'
                },
                'shops': {
                    'feature_types': ['shop'],
                    'query_type': 'accessible_pois'
                },
                'transport': {
                    'feature_types': ['public_transport', 'highway'],
                    'query_type': 'accessible_pois'
                },
                'tourism': {
                    'feature_types': ['tourism'],
                    'query_type': 'accessible_pois'
                },
                'leisure': {
                    'feature_types': ['leisure'],
                    'query_type': 'accessible_pois'
                },
                'routing_infrastructure': {
                    'feature_types': ['routing'],
                    'query_type': 'accessibility_routing'
                }
            },
            
            # Special collections
            "special_collections": {
                "pedestrian_widths": {
                    "enabled": True,
                    "description": "Pedestrian area width data for accessibility routing"
                }
            }
        }
    
    def _setup_arcgis_config(self) -> Dict[str, Any]:
        """Setup ArcGIS data configuration."""
        urls_file = self.project_root / "rampa" / "data" / "urls.json"
        
        return {
            "urls_file": str(urls_file),
            "enabled": True,  # Currently disabled in setup
            "populate": True
        }
    
    def _setup_logging_config(self) -> Dict[str, Any]:
        """Setup logging configuration."""
        return {
            "level": "INFO",
            "format": "{time:HH:mm:ss} | {level} | {message}",
            "file_pattern": "file_{time}.log"
        }
    
    def _setup_transform_config(self) -> Dict[str, Any]:
        """Setup transformation pipeline configuration."""
        transform_dir = self.project_root / "rampa" / "duckdb" / "transfrom"
        
        return {
            "transform_dir": str(transform_dir),
            "script_pattern": "step_*.py",
            "execution_order": "filename",  # Order by filename (step_01, step_02, etc.)
            
            # Expected transformation scripts
            "expected_scripts": [
                "step_01_clean_and_standardize.py",
                "step_02_geography_dimension.py", 
                "step_02_geospatial_processing.py",
                "step_03_demographics_indicators.py",
                "step_03_demographics_normalization.py",
                "step_05_poi_unification.py"
            ]
        }
    
    # Convenience methods for getting paths
    def get_db_path(self, db_name: str) -> str:
        """Get database path for connection (without .db extension)."""
        return self.db_config["databases"].get(db_name)
    
    def get_db_file_path(self, db_name: str) -> str:
        """Get database file path (with .db extension)."""
        return self.db_config["database_files"].get(db_name)
    
    def get_madrid_bbox(self) -> tuple:
        """Get Madrid bounding box coordinates."""
        return self.osm_config["madrid_bbox"]
    
    def get_osm_layers(self) -> Dict[str, Dict]:
        """Get OSM layer configuration."""
        return self.osm_config["layers"]
    
    def get_transform_dir(self) -> str:
        """Get transformation scripts directory."""
        return self.transform_config["transform_dir"]
    
    def ensure_directories(self):
        """Ensure all required directories exist."""
        # Create database directory
        db_dir = Path(self.db_config["base_dir"])
        db_dir.mkdir(parents=True, exist_ok=True)
        
        # Create transform directory (should already exist)
        transform_dir = Path(self.transform_config["transform_dir"])
        if not transform_dir.exists():
            print(f"Warning: Transform directory not found: {transform_dir}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary with relative paths."""
        return {
            "project_root": ".",  # Always use relative path for portability
            "database": {
                "base_dir": "rampa/duckdb/databases",
                "databases": {
                    "arcgis": "rampa/duckdb/databases/madrid_layers",
                    "osm": "rampa/duckdb/databases/madrid_osm",
                    "final": "rampa/duckdb/databases/rampa", 
                    "test": "rampa/duckdb/databases/test"
                },
                "database_files": {
                    "arcgis": "rampa/duckdb/databases/madrid_layers.db",
                    "osm": "rampa/duckdb/databases/madrid_osm.db",
                    "final": "rampa/duckdb/databases/rampa.db",
                    "test": "rampa/duckdb/databases/test.db"
                },
                "creation_order": self.db_config["creation_order"]
            },
            "osm": self.osm_config,
            "arcgis": {
                "urls_file": "rampa/data/urls.json",
                "enabled": self.arcgis_config["enabled"],
                "populate": self.arcgis_config["populate"]
            },
            "transform": {
                "transform_dir": "rampa/duckdb/transfrom",
                "script_pattern": self.transform_config["script_pattern"],
                "execution_order": self.transform_config["execution_order"],
                "expected_scripts": self.transform_config["expected_scripts"]
            }
        }
    
    def save_config(self, filepath: str = None):
        """Save configuration to TOML file."""
        if filepath is None:
            filepath = self.project_root / "config.toml"
        
        config_dict = {
            "project": {
                "name": "Madrid Open Data",
                "description": "Accessibility data analysis for Madrid",
                "version": "1.0.0"
            },
            "database": {
                "base_dir": "rampa/duckdb/databases",
                "names": {
                    "arcgis": "madrid_layers",
                    "osm": "madrid_osm", 
                    "final": "rampa",
                    "test": "test"
                },
                "creation_order": self.db_config.get("creation_order", ["arcgis", "osm", "final"])
            },
            "osm": self.osm_config,
            "arcgis": self.arcgis_config,
            "transform": self.transform_config,
            "logging": getattr(self, 'logging_config', {
                "level": "INFO",
                "format": "{time:HH:mm:ss} | {level} | {message}",
                "file_pattern": "file_{time}.log"
            }),
            "paths": {
                "data_dir": "rampa/data",
                "notebooks_dir": "notebooks",
                "reports_dir": "reports", 
                "models_dir": "models"
            }
        }
        
        with open(filepath, 'wb') as f:
            tomli_w.dump(config_dict, f)
    
    @classmethod
    def load_config(cls, filepath: str):
        """Load configuration from TOML file."""
        # Determine project root from config file location
        config_path = Path(filepath)
        if config_path.name == "config.toml":
            project_root = config_path.parent
        else:
            project_root = config_path.parent
            
        instance = cls(project_root=str(project_root), config_file=filepath)
        return instance

# Global configuration instance
config = MadridDataConfig()

# Convenience functions for backward compatibility
def get_db_path(db_name: str) -> str:
    """Get database path for connection."""
    return config.get_db_path(db_name)

def get_db_file_path(db_name: str) -> str:
    """Get database file path."""
    return config.get_db_file_path(db_name)

def get_madrid_bbox() -> tuple:
    """Get Madrid bounding box."""
    return config.get_madrid_bbox()

def get_osm_layers() -> Dict[str, Dict]:
    """Get OSM layer configuration."""
    return config.get_osm_layers()

# Database paths for easy import
DB_PATHS = config.db_config["databases"]
DB_FILES = config.db_config["database_files"]

if __name__ == "__main__":
    # Demo/test the configuration
    print("=== MADRID OPEN DATA CONFIGURATION ===")
    print(f"Project root: {config.project_root}")
    print(f"Database directory: {config.db_config['base_dir']}")
    print("\nDatabase paths:")
    for name, path in config.db_config["databases"].items():
        print(f"  {name}: {path}")
    
    print(f"\nMadrid bbox: {config.get_madrid_bbox()}")
    print(f"OSM layers: {list(config.get_osm_layers().keys())}")
    
    # Save configuration as TOML
    config.save_config()
    print(f"\nConfiguration saved to: {config.project_root}/config.toml")
>>>>>>> 433b687 (Refactor geospatial processing and demographics scripts; improve error handling and logging)
