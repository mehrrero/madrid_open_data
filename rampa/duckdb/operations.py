import os
import pickle
from typing import List, Tuple, Dict, Any
from .connection import DuckDBPyConnection


PickleCache = Dict[Tuple[str, str], Dict[str, Any]]  # Changed from List[float] to Dict[str, Any]


def write_layer_to_table(
    con: DuckDBPyConnection, layer_name: str, source: str, layer_data: Dict[str, Any]
) -> DuckDBPyConnection:
    """
    Writes the given map layer to the `map_layers` table in the database.

    Args:
        con (DuckDBPyConnection): The connection to the DuckDB database.
        layer_name (str): The name of the map layer.
        source (str): The source of the layer data (e.g., API endpoint, file name).
        layer_data (Dict[str, Any]): The layer data (GeoJSON, metadata, etc.).

    Returns:
        DuckDBPyConnection: The connection to the DuckDB database after the insertion.
    """
    create_table_if_not_exists(con)
    # Convert layer_data to JSON string for storage
    import json
    layer_json = json.dumps(layer_data)
    con.execute("INSERT INTO map_layers VALUES (?, ?, ?)", [layer_name, source, layer_json])
    return con


def create_table_if_not_exists(con) -> None:
    """
    Creates a table named `map_layers` if it doesn't already exist in the database.

    Args:
        con: The database connection object.

    Returns:
        None
    """
    con.execute(
        "CREATE TABLE IF NOT EXISTS map_layers (layer_name VARCHAR, source VARCHAR, layer_data JSON)"
    )


def is_key_in_table(con: DuckDBPyConnection, key: Tuple[str, str]) -> bool:
    """
    Check if a key exists in the map_layers table.

    Args:
        con (DuckDBPyConnection): The connection to the DuckDB database.
        key (Tuple[str, str]): The key to check in the format (layer_name, source).

    Returns:
        bool: True if the key exists in the table, False otherwise.
    """
    create_table_if_not_exists(con)
    result = con.execute(
        "SELECT EXISTS(SELECT * FROM map_layers WHERE layer_name=? AND source=?)",
        [key[0], key[1]],
    ).fetchone()
    if result:
        return result[0]
    return False


def list_keys_in_table(
    con: DuckDBPyConnection, keys: List[Tuple[str, str]]
) -> list[tuple[str, str]]:
    """
    Returns a list of keys that exist in the specified table.

    Args:
        con (DuckDBPyConnection): The connection to the DuckDB database.
        keys (List[Tuple[str, str]]): The keys to check in the table.

    Returns:
        List[Tuple[str, str]]: A list of keys that exist in the table.
    """
    keys_in_table = []

    for key in keys:
        if is_key_in_table(con, key):
            keys_in_table.append(key)
    return keys_in_table


def load_pickle_cache(pickle_path: str) -> PickleCache:
    """
    Load a pickle cache from the given file path.

    Args:
        pickle_path (str): The path to the pickle file.

    Returns:
        PickleCache: The loaded pickle cache.

    """
    if os.path.exists(pickle_path):
        with open(pickle_path, "rb") as file:
            return pickle.load(file)
    return {}


def write_pickle_cache_to_duckdb(con: DuckDBPyConnection, pickle_path: str) -> None:
    """
    Writes the contents of a pickle cache to a DuckDB database.

    Args:
        con (DuckDBPyConnection): The connection to the DuckDB database.
        pickle_path (str): The path to the pickle cache file.

    Returns:
        None
    """
    cache = load_pickle_cache(pickle_path)
    create_table_if_not_exists(con)
    for key, value in cache.items():
        write_layer_to_table(con, key[0], key[1], value)


def save_pickle_cache(cache: PickleCache, cache_path: str) -> None:
    """
    Save the given cache object as a pickle file.

    Args:
        cache (PickleCache): The cache object to be saved.
        cache_path (str): The path to save the pickle file.

    Returns:
        None
    """
    with open(cache_path, "wb") as file:
        pickle.dump(cache, file)


def get_layer_from_table(con: DuckDBPyConnection, layer_name: str, source: str) -> Dict[str, Any]:
    """
    Retrieves the layer data from the 'map_layers' table based on the given layer name and source.

    Args:
        con (DuckDBPyConnection): The connection to the DuckDB database.
        layer_name (str): The name to search for in the 'layer_name' column of the table.
        source (str): The source to search for in the 'source' column of the table.

    Returns:
        Dict[str, Any]: The layer data associated with the given layer name and source.

    Raises:
        ValueError: If the layer for the given name and source is not found in the table.
    """
    result = con.execute(
        "SELECT layer_data FROM map_layers WHERE layer_name=? AND source=?", [layer_name, source]
    ).fetchone()
    if result:
        import json
        return json.loads(result[0])
    raise ValueError(f"Layer {layer_name} from source {source} not found in table")


def get_all_layers(con: DuckDBPyConnection) -> List[Dict[str, Any]]:
    """
    Retrieves all layers from the map_layers table.

    Args:
        con (DuckDBPyConnection): The connection to the DuckDB database.

    Returns:
        List[Dict[str, Any]]: A list of all layers with their metadata.
    """
    create_table_if_not_exists(con)
    result = con.execute("SELECT layer_name, source, layer_data FROM map_layers").fetchall()
    
    layers = []
    for row in result:
        import json
        layer_info = {
            'layer_name': row[0],
            'source': row[1],
            'layer_data': json.loads(row[2])
        }
        layers.append(layer_info)
    
    return layers


def delete_layer_from_table(con: DuckDBPyConnection, layer_name: str, source: str) -> bool:
    """
    Deletes a layer from the map_layers table.

    Args:
        con (DuckDBPyConnection): The connection to the DuckDB database.
        layer_name (str): The name of the layer to delete.
        source (str): The source of the layer to delete.

    Returns:
        bool: True if the layer was deleted, False if it wasn't found.
    """
    if not is_key_in_table(con, (layer_name, source)):
        return False
    
    con.execute(
        "DELETE FROM map_layers WHERE layer_name=? AND source=?", [layer_name, source]
    )
    return True