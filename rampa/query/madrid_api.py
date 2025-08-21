import geopandas as gpd
import matplotlib.pyplot as plt

class GeoDataset:
    def __init__(self, url: str):
        """
        Inicializa la clase con la URL o ruta local de un dataset geoespacial.
        """
        self.url = url
        self.gdf = None

        try:
            self.gdf = gpd.read_file(self.url)
            print(f"Dataset cargado con {len(self.gdf)} registros.")
        except Exception as e:
            print(f"Error al cargar el dataset: {e}")

    