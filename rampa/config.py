#!/usr/bin/env python3
"""
Central Configuration for Madrid Open Data Project
"""

from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
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
            self.paths = data.get('paths', {})
            self.madrid_api = data.get('madrid_api', {})
            self.data_analysis = data.get('data_analysis', {})

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
