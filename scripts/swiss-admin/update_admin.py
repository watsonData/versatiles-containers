import os
import geopandas as gpd
from shapely.ops import unary_union, linemerge
import docker

client = docker.from_env()

# config
BFS_URL = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/35130777/master"
LAKE_LAYER = "K4seen_yyymmdd11"
CANTON_LAYER = "K4kant_20220101_gf_ohne_Seen"
MUNICIPALITY_LAYER = "K4voge_20250604_gf"
VOTING_DISTRICT_LAYER = "zaehlkreise_ZH_Wint " # space at the end is intentional

if not os.path.exists("./tmp"):
    os.makedirs("./tmp")

# load large lakes first, so we can subtract them from other layers
gdf_lakes = gpd.read_file(f"TOPOJSON:{BFS_URL}", layer=LAKE_LAYER)
gdf_lakes = gdf_lakes.set_crs(epsg=2056)

# load cantons
gdf_canton = gpd.read_file(f"TOPOJSON:{BFS_URL}", layer=CANTON_LAYER)
gdf_canton = gdf_canton.set_crs(epsg=2056)

# create canton borders by dissolving all canton boundaries and subtracting the outer boundary
all_boundaries = unary_union(gdf_canton.boundary.values)
outer_boundary = unary_union(gdf_canton.geometry.values).boundary

internal = all_boundaries.difference(outer_boundary)

internal = linemerge(internal)

gdf_internal = gpd.GeoDataFrame(geometry=[internal], crs=gdf_canton.crs) \
                .explode(index_parts=False) \
                .reset_index(drop=True)

gdf_internal = gdf_internal[gdf_internal.length > 0]

gdf_internal = gdf_internal.overlay(gdf_lakes, how='difference')

gdf_internal = gdf_internal.to_crs(epsg=4326)
gdf_internal[["geometry"]].to_file("./tmp/canton-borders.geojson", driver="GeoJSON")

# subtract lakes from cantons
gdf_canton = gdf_canton.overlay(gdf_lakes, how='difference')

gdf_canton = gdf_canton.to_crs(epsg=4326)
gdf_canton.drop(columns=["id"]).rename(columns={"kantId": "id"})[["id", "geometry"]].to_file("./tmp/cantons.geojson", driver="GeoJSON")

# load municipalities
gdf_municipality = gpd.read_file(f"TOPOJSON:{BFS_URL}", layer=MUNICIPALITY_LAYER)
gdf_municipality = gdf_municipality.set_crs(epsg=2056)

gdf_municipality = gdf_municipality.to_crs(epsg=4326)
gdf_municipality.drop(columns=["id"]).rename(columns={"vogeId": "id", "kantId": "parentId"})[["id", "parentId", "geometry"]].to_file("./tmp/municipalities.geojson", driver="GeoJSON")

# load voting districts (only for Zurich/Winterthur)
gdf_voting_district = gpd.read_file(f"TOPOJSON:{BFS_URL}", layer=VOTING_DISTRICT_LAYER)
gdf_voting_district = gdf_voting_district.set_crs(epsg=2056)

gdf_voting_district = gdf_voting_district.to_crs(epsg=4326)
gdf_voting_district.rename(columns={"bezkId": "parentId"})[["id", "parentId", "geometry"]].to_file("./tmp/voting-districts.geojson", driver="GeoJSON")

print("Building Docker image...")
client.images.build(path=".", tag="watson-ddj/geo:latest", rm=True)

# Command to generate mbtiles using tippecanoe
tippecanoe_command = [
    "bash", "-c",
    "tippecanoe -o /data/cantons.mbtiles /data/cantons.geojson --force && " +
    'tippecanoe -o /data/voting-districts.mbtiles -L\'{"layer":"voting-districts", "file":"/data/voting-districts.geojson"}\' --force && ' +
    'tippecanoe -o /data/municipalities.mbtiles /data/municipalities.geojson -L\'{"layer":"canton-borders", "file":"/data/canton-borders.geojson"}\' --force &&' +
    "versatiles convert /data/cantons.mbtiles /data/cantons.versatiles && " +
    "versatiles convert /data/municipalities.mbtiles /data/municipalities.versatiles && " +
    "versatiles convert /data/voting-districts.mbtiles /data/voting-districts.versatiles"
]

print("Running Docker image...")
print(client.containers.run(
    image="watson-ddj/geo:latest",
    command=tippecanoe_command,
    remove=True,
    stdout=True,
    stderr=True,
    tty=True,
    volumes={os.path.abspath("./tmp"): {'bind': '/data', 'mode': 'rw'}},
).decode("utf-8"))
