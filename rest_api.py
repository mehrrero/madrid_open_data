from fastapi import FastAPI
<<<<<<< HEAD
<<<<<<< HEAD
from rampa.routing.route import Network, geocoder, ruta_to_json

=======
from rampa.routing.route import Network
>>>>>>> d6db040 (routing api done)
=======
from rampa.routing.route import Network
>>>>>>> fc49f44 (routing api done)

app = FastAPI()
network = Network(db='rampa/data/grafo.db', db_alt='rampa/data/grafo_alt.db')

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
<<<<<<< HEAD
<<<<<<< HEAD
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
=======
=======
>>>>>>> fc49f44 (routing api done)
    ruta_json = ruta.to_json()
    ruta_alt_json = ruta_alt.to_json()
    
    return {
        "ruta": ruta_json,
        "ruta_alt": ruta_alt_json
<<<<<<< HEAD
    }
>>>>>>> d6db040 (routing api done)
=======
    }
>>>>>>> fc49f44 (routing api done)
