from sqlalchemy import Column, Integer, String, Float, Text, Sequence, Boolean
from sqlalchemy import create_engine, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.schema import PrimaryKeyConstraint


DATABASE_URL = "duckdb:///rampa/duckdb/databases/rampa.db"
engine = create_engine(DATABASE_URL, echo=True)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()


# define a sequence for the autoincrementing id
poi_id_seq = Sequence("fact_points_of_interest_id_seq")
node_id_seq = Sequence("nodes_id_seq")
edge_id_seq = Sequence("edges_id_seq")

class DimGeography(Base):
    """
    Dimensional table for geographical data, linking districts, neighborhoods,
    and census sections. This helps in spatial joins and lookups.
    """
    __tablename__ = "dim_geography"

    district_id = Column(String, nullable=False)
    district_name = Column(Text)
    neighborhood_name = Column(Text)
    census_section_id = Column(String, primary_key=True, nullable=False)
    geom = Column(Text)  # Storing geometry as a Well-Known Text (WKT) string

class FactDemographics(Base):
    """
    Fact table containing summary demographic data, such as total population
    and indices. It is linked to DimGeography.
    """
    __tablename__ = "fact_demographics"

    # Use census_section_id from the original data as the primary key
    census_section_id = Column(String, ForeignKey("dim_geography.census_section_id"), primary_key=True)

    # Summary Demographic data
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


class FactDemographicsAgeGroups(Base):
    """
    Fact table to hold a normalized representation of population by age group.
    This structure is more flexible for analysis.
    """
    __tablename__ = "fact_demographics_age_groups"
    __table_args__ = (
        PrimaryKeyConstraint('census_section_id', 'age_group'),
    )

    # Foreign key to the main demographics table
    census_section_id = Column(String, ForeignKey("fact_demographics.census_section_id"), nullable=False)
    age_group = Column(Text, nullable=False)  # e.g., '00_04_años', '85_89_años'
    population_count = Column(Integer)

class FactPointsOfInterest(Base):
    """
    Unified table for all points of interest from both ArcGIS and OSM.
    Includes accessibility information.
    """
    __tablename__ = "fact_points_of_interest"

    poi_id = Column(
        Integer,
        poi_id_seq,
        server_default=poi_id_seq.next_value(),
        primary_key=True,
        nullable=False,
    )
    source = Column(String, nullable=False)  # 'arcgis' or 'osm'
    name = Column(Text)
    description = Column(Text)
    category = Column(Text)
    wheelchair_accessible = Column(String)  # 'yes', 'no', or 'limited'
    address = Column(Text)
    geom = Column(Text)

# --- Tables for the Routing Service ---

class Nodes(Base):
    """
    Represents intersections and key points in the road network.
    """
    __tablename__ = "nodes"

    node_id = Column(
        Integer,
        node_id_seq,
        server_default=node_id_seq.next_value(),
        primary_key=True,
        nullable=False,
    )
    geom = Column(Text, nullable=False)  # Stores the point geometry
    is_accessible = Column(Boolean)

class Edges(Base):
    """
    Represents road segments connecting nodes, with attributes relevant to
    wheelchair accessibility and routing.
    """
    __tablename__ = "edges"

    edge_id = Column(
        Integer,
        edge_id_seq,
        server_default=edge_id_seq.next_value(),
        primary_key=True,
        nullable=False,
    )
    # Use foreign keys to link to the 'nodes' table
    from_node_id = Column(Integer, ForeignKey("nodes.node_id"), nullable=False)
    to_node_id = Column(Integer, ForeignKey("nodes.node_id"), nullable=False)

    length_m = Column(Float)
    is_wheelchair_accessible = Column(Boolean, nullable=False)
    incline_grade = Column(Float)
    surface_type = Column(String)
    road_type = Column(String)

    # Define relationships to the Nodes table for easier querying
    from_node = relationship("Nodes", foreign_keys=[from_node_id], backref="out_edges")
    to_node = relationship("Nodes", foreign_keys=[to_node_id], backref="in_edges")


Base.metadata.create_all(engine)
