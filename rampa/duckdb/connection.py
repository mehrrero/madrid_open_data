import duckdb
from duckdb import DuckDBPyConnection

def open_connection(dbname=None) -> duckdb.DuckDBPyConnection:
    """
    Connects to a local duckdb database and returns a connection object.

    Args:
        dbname (str, optional): The name of the database to connect to. If not provided, a connection to an in-memory database will be established.

    Returns:
        `duckdb.DuckDBPyConnection`: A connection object to the local database.
    """
    if dbname:
        # Don't add .db if it's already there
        if not dbname.endswith('.db'):
            return duckdb.connect(f"{dbname}.db")
        else:
            return duckdb.connect(dbname)
    else:
        return duckdb.connect(":memory:")


def load_extension(
    con: duckdb.DuckDBPyConnection, extension: str
) -> DuckDBPyConnection:
    """
    Loads and installs a DuckDB extension in the given connection.

    Args:
        con (`duckdb.DuckDBPyConnection`): The DuckDB connection.
        extension (str): The name of the extension to load.

    Returns:
        `duckdb.DuckDBPyConnection`: The modified DuckDB connection.

    Raises:
        Any exception raised during the installation or loading of the extension.
    """
    try:
        con.install_extension(extension)
        con.load_extension(extension)
    except:
        print(f"Could not load extension {extension}")
        pass
    return con

def get_duckdb_connection(dbname: str = None) -> duckdb.DuckDBPyConnection:
    """
    Convenience function to get a DuckDB connection with common extensions loaded.
    
    Args:
        dbname (str, optional): The name of the database to connect to.
        
    Returns:
        duckdb.DuckDBPyConnection: A connection object to the database.
    """
    con = open_connection(dbname)
    
    # Load common extensions for geospatial work
    load_extension(con, "spatial")
    load_extension(con, "json")

    return con