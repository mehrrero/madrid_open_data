from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from rampa.routing.route import Network, geocoder, ruta_to_json
import duckdb
import json
import pandas as pd
import math
from typing import List, Optional
from rampa.config import config



app = FastAPI()
network = Network(db=config.paths['grafo_db'])
db_connection = duckdb.connect(config.paths['pois_db'])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    print("App is starting…")

@app.on_event("shutdown")
def shutdown_event():
    db_connection.close()
    print("DB closed.")



@app.post("/ruta")
async def create_route(x1: float, y1: float, x2: float, y2: float):
    """
    Asynchronously creates primary and alternate routes between two coordinates using the network module.
    Args:
        x1 (float): Longitude of the starting point.
        y1 (float): Latitude of the starting point.
        x2 (float): Longitude of the destination point.
        y2 (float): Latitude of the destination point.
    Returns:
        dict: A dictionary containing GeoJSON representations of the primary route ('ruta') and the alternate route ('ruta_alt').
    Raises:
        Any exceptions raised by the underlying network.route_gdf or GeoDataFrame to_json methods.
    """
    
    coord1 = (x1, y1)  
    coord2 = (x2, y2)
    ruta = network.route_gdf(coord1, coord2, alternate=False)
    ruta_alt = network.route_gdf(coord1, coord2, alternate=True)
    
    # Convert GeoDataFrames to GeoJSON-like dicts
    ruta_json = ruta_to_json(ruta)
    ruta_alt_json = ruta_to_json(ruta_alt)

    return {
        "ruta": ruta_json,
        "ruta_alt": ruta_alt_json
    }
    

@app.post("/geocoder")
async def geocode_address(query: str):
    """
    Asynchronously geocodes a given address query string.
    Args:
        query (str): The address or location to geocode.
    Returns:
        dict: A dictionary containing the geocoding results under the "results" key.
    """
    
    results = geocoder(query)
    return {"results": results}




@app.get("/tables/{table_name}")
async def get_table(table_name: str):
    df = db_connection.execute(f"SELECT * FROM {table_name}").fetchdf()
    # Convert DataFrame to list of dicts
    records = df.to_dict(orient="records")

    # Recursively replace NaN and infinite values with None
    def clean_value(v):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return v

    cleaned_records = [
        {k: clean_value(v) for k, v in record.items()}
        for record in records
    ]

    return cleaned_records

@app.get("/layers/{layer_name}")

async def get_layer(layer_name: str):
    """
    Layer names in fact_demographics table:

    total_population = Column(Integer)
    density = Column(Float)
    edad_promedio = Column(Float)
    proporcion_juventud = Column(Float)
    proporcion_envejecimiento = Column(Float)
    proporcion_sobreenvejecimiento = Column(Float)
    indice_envejecimiento = Column(Float)
    indice_juventud = Column(Float)
    indice_dependencia = Column(Float)
    indice_estructura_poblacion_act = Column(Float)
    indice_reemplazo_poblacion_acti = Column(Float)
    razon_progresividad_demografica = Column(Float)
    """
    # Join fact_demographics with dim_geography to get geometry (geom) for each census_section_id
    df = db_connection.execute(
        f"""
        SELECT fd.census_section_id, fd.{layer_name}, dg.geom
        FROM fact_demographics fd
        JOIN dim_geography dg
        ON fd.census_section_id = dg.census_section_id
        """
    ).fetchdf()
    # Convert DataFrame to list of dicts
    records = df.to_dict(orient="records")

    # Recursively replace NaN and infinite values with None
    def clean_value(v):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return v

    cleaned_records = [
        {k: clean_value(v) for k, v in record.items()}
        for record in records
    ]

    return cleaned_records


@app.get("/pois")
async def get_pois(
    category: Optional[str] = Query(
        None, 
        description="Filter by specific category",
        enum=[
            "all",
            "CentrosSalud",
            "ResidenciasApartamentosMayores", 
            "CentrosDiaMayores",
            "ParquesJardines",
            "CentrosServiciosSociales",
            "OficinasCorreos"
        ]
    ),
    accessibility: Optional[str] = Query(
        None, 
        description="Filter by accessibility: '0' (not accessible) or '1' (accessible - any value > 0)",
        enum=["0", "1"]
    ),
    limit: Optional[int] = Query(1000, description="Maximum number of POIs to return")
):
    """
    Get essential services POIs: farmacias, centros de salud, residencias, 
    centros de dias, parques y jardines, servicios sociales, bancos.
    """
    
    # Define the category mappings
    category_mappings = {
        "CentrosSalud": "/contenido/entidadesYorganismos/CentrosAtencionMedica/CentrosSalud",
        "ResidenciasApartamentosMayores": "/contenido/entidadesYorganismos/CentrosAtencionSocialMayores/ResidenciasApartamentosMayores",
        "CentrosDiaMayores": "/contenido/entidadesYorganismos/CentrosAtencionSocialMayores/CentrosDiaMayores",
        "ParquesJardines": "/contenido/entidadesYorganismos/ParquesJardines",
        "CentrosServiciosSociales": "/contenido/entidadesYorganismos/CentrosAtencionSocial/CentrosServiciosSociales",
        "OficinasCorreos": "/contenido/entidadesYorganismos/OficinasCorreos"
    }
    
    # Build the SQL query
    if category and category != "all":
        # Filter by specific category
        if category in category_mappings:
            db_category = category_mappings[category]
            base_query = """
                SELECT 
                    PK as poi_id,
                    NOMBRE as name,
                    TIPO as category,
                    ACCESIBILIDAD as wheelchair_accessible,
                    "NOMBRE-VIA" as address,
                    LATITUD as latitude,
                    LONGITUD as longitude,
                    DESCRIPCION as description,
                    DISTRITO as district,
                    BARRIO as neighborhood
                FROM pois
                WHERE TIPO = ?
            """
            params = [db_category]
        else:
            # Invalid category
            return []
    else:
        # Get all essential services
        essential_categories = list(category_mappings.values())
        placeholders = ','.join(['?' for _ in essential_categories])
        base_query = f"""
            SELECT 
                PK as poi_id,
                NOMBRE as name,
                TIPO as category,
                ACCESIBILIDAD as wheelchair_accessible,
                "NOMBRE-VIA" as address,
                LATITUD as latitude,
                LONGITUD as longitude,
                DESCRIPCION as description,
                DISTRITO as district,
                BARRIO as neighborhood
            FROM pois
            WHERE TIPO IN ({placeholders})
        """
        params = essential_categories.copy()
    
    # Add accessibility filter
    if accessibility:
        if accessibility == "0":
            # Not accessible (exactly 0)
            base_query += " AND ACCESIBILIDAD = '0'"
        elif accessibility == "1":
            # Accessible (any value greater than 0)
            base_query += " AND ACCESIBILIDAD != '0' AND ACCESIBILIDAD IS NOT NULL"
    
    # Add limit
    base_query += f" LIMIT ?"
    params.append(str(limit if limit is not None else 1000))
    
    try:
        # Execute query
        df = db_connection.execute(base_query, params).fetchdf()
        
        # Convert DataFrame to list of dicts
        records = df.to_dict(orient="records")
        
        # Clean NaN and infinite values
        def clean_value(v):
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                return None
            return v
        
        cleaned_records = [
            {k: clean_value(v) for k, v in record.items()}
            for record in records
        ]
        
        return cleaned_records
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/pois/categories")
async def get_poi_categories():
    """
    Get available POI categories with counts for the frontend dropdown.
    """
    try:
        # Define the category mappings with human-readable names
        category_info = {
            "CentrosSalud": {
                "name": "Centros de Salud",
                "db_value": "/contenido/entidadesYorganismos/CentrosAtencionMedica/CentrosSalud",
                "description": "Health Centers"
            },
            "ResidenciasApartamentosMayores": {
                "name": "Residencias",
                "db_value": "/contenido/entidadesYorganismos/CentrosAtencionSocialMayores/ResidenciasApartamentosMayores",
                "description": "Nursing Homes & Apartments"
            },
            "CentrosDiaMayores": {
                "name": "Centros de Día",
                "db_value": "/contenido/entidadesYorganismos/CentrosAtencionSocialMayores/CentrosDiaMayores",
                "description": "Day Centers"
            },
            "ParquesJardines": {
                "name": "Parques y Jardines",
                "db_value": "/contenido/entidadesYorganismos/ParquesJardines",
                "description": "Parks & Gardens"
            },
            "CentrosServiciosSociales": {
                "name": "Servicios Sociales",
                "db_value": "/contenido/entidadesYorganismos/CentrosAtencionSocial/CentrosServiciosSociales",
                "description": "Social Services"
            },
            "OficinasCorreos": {
                "name": "Oficinas de Correos",
                "db_value": "/contenido/entidadesYorganismos/OficinasCorreos",
                "description": "Post Offices"
            }
        }
        
        # Get counts for each category
        categories_with_counts = []
        for key, info in category_info.items():
            count = db_connection.execute(
                "SELECT COUNT(*) as count FROM pois WHERE TIPO = ?", 
                [info["db_value"]]
            ).fetchone()[0]
            
            categories_with_counts.append({
                "value": key,
                "label": info["name"],
                "description": info["description"],
                "count": count
            })
        
        return {
            "categories": categories_with_counts,
            "total_categories": len(categories_with_counts)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")



@app.get("/edge/{ID}")
async def get_edge_data(ID: str):
    """
    Get data for a specific edge by its ID.
    """
    try:
        edge_data = db_connection.execute(
            "SELECT * FROM edges WHERE ID = ?", [ID]
        ).fetchone()

        if edge_data is None:
            raise HTTPException(status_code=404, detail="Edge not found")

        return edge_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
