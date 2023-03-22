import arcgis
from arcgis.geometry import Geometry, filters
import numpy as np

# url = "https://fs.regrid.com/FyFo8GvQNgqmZSusYuomkU434eAxFXXd6Nz6xrRKwcjsMVT7aeLobsiL2as8Z5LV/rest/services/premium/FeatureServer/" # NON-ESRI HOSTED FEATURE SERVICE URL (PROBLEMATIC SPATIAL QUERY)
url = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/Minnesota_Census_2020_Redistricting_Blocks/FeatureServer" # OTHER ESRI HOSTED FEATURE SERVICE URL

# CREATE FEATURE LAYER FROM URL
feature_layer_collection = arcgis.features.FeatureLayerCollection(url)
feature_layer = feature_layer_collection.layers[0]
feature_layer_wkid = feature_layer.properties.extent.spatialReference.wkid

# CREATE EMPTY POINTS LAYER
points_layer_out = r"memory\points_layer"
arcpy.management.CreateFeatureclass(r"memory", "points_layer", "POINT", spatial_reference=feature_layer_wkid)
points_layer = arcpy.management.MakeFeatureLayer(points_layer_out, "points_layer")

if feature_layer_wkid == 4326:
    point_coordinates = [
        (-93.9131369009999, 44.210425959),
        (-94.0884167979999, 43.738621476),
        (-95.7195835559999, 43.711855544),
        (-95.4526783869999, 43.709149296),
        (-95.3199124369999, 45.182045665),
        (-95.1405768829999, 43.67125143),
        (-95.1290473599999, 44.54203084),
        (-94.9838135219999, 43.631843742),
        (-96.3840971469999, 45.007283328)
    ]

elif feature_layer_wkid == 102100:
    point_coordinates = [
        (-10454362.58, 5498064.041),
        (-10473874.65, 5425081.951),
        (-10655455.3, 5420958.907),
        (-10625743.55, 5420542.138),
        (-10610964.11, 5650226.525),
        (-10591000.57, 5414707.734),
        (-10589717.11, 5549709.47),
        (-10573549.7549, 5408644.798500001),
        (-10729428.615, 5622668.17)
    ]

# INSERT POINTS INTO POINTS LAYER
with arcpy.da.InsertCursor(points_layer, ['SHAPE@XY']) as cursor:
    for point in point_coordinates:
        cursor.insertRow([point])

# CREATE BUFFER AROUND POINTS
points_buffer_out = r"memory\points_buffer"
arcpy.analysis.Buffer(points_layer, points_buffer_out, "1 Miles", method="Geodesic (shape preserving)")
points_buffer = arcpy.management.MakeFeatureLayer(points_buffer_out, "points_buffer")

# CALCULATE GEOMETRY ATTRIBUTES
arcpy.management.CalculateGeometryAttributes(
    points_buffer,
    geometry_property="xmin EXTENT_MIN_X;ymin EXTENT_MIN_Y;xmax EXTENT_MAX_X;ymax EXTENT_MAX_Y",
    coordinate_system=feature_layer_wkid)

expression_envelope = ("""'{"xmin":'+str(!xmin!)+',"ymin":'+str(!ymin!)+""" +
                                    """',"xmax":'+str(!xmax!)+',"ymax":'+str(!ymax!)+""" +
                                    """',"spatialReference":{"wkid":'""" +
                                    '"{0}"'.format(feature_layer_wkid) + '"}}"')

expression_polygon = ("""'{"rings":[[['+str(!xmin!)+','+str(!ymin!)+""" +
                        """'],['+str(!xmax!)+','+str(!ymin!)+""" +
                        """'],['+str(!xmax!)+','+str(!ymax!)+""" +
                        """'],['+str(!xmin!)+','+str(!ymax!)+""" +
                        """'],['+str(!xmin!)+','+str(!ymin!)+""" +
                        """']]],"spatialReference":{"wkid":'""" +
                        '"{0}"'.format(feature_layer_wkid) + '"}}"')

arcpy.management.CalculateField(
        points_buffer,
        field="geometry_envelope",
        expression=expression_envelope,
        field_type="TEXT")

arcpy.management.CalculateField(
        points_buffer,
        field="geometry_polygon",
        expression=expression_polygon,
        field_type="TEXT")

# CREATE EMPTY FEATURE LAYER SHELL
feature_layer_shell_out = r"memory\feature_layer_shell"
arcpy.management.CreateFeatureclass(r"memory", "feature_layer_shell", "POLYGON", spatial_reference=feature_layer_wkid)
feature_layer_shell = arcpy.management.MakeFeatureLayer(feature_layer_shell_out, "feature_layer_shell")

# QUERY FEATURE LAYER AND INSERT FEATURES INTO FEATURE LAYER SHELL
with arcpy.da.InsertCursor(feature_layer_shell, ['Shape@']) as insert_cursor:
    with arcpy.da.SearchCursor(points_buffer, ['geometry_envelope', 'geometry_polygon']) as search_cursor:
        for row in search_cursor:

            geometry_filter = Geometry(row[0])  # USE ENVELOPE
            # geometry_filter = Geometry(row[1])  # USE POLYGON

            feature_set = feature_layer.query(
                where='1=1',
                geometry_filter=filters.envelope_intersects(  # USE ENVELOPE
                # geometry_filter=filters.intersects(  # USE POLYGON
                    geometry_filter, sr=feature_layer_wkid))
            arcpy.AddMessage('features count: ' + str(len(feature_set.features)))

            count = feature_layer.query(
                geometry_filter=filters.envelope_intersects(  # USE ENVELOPE
                # geometry_filter=filters.intersects(  # USE POLYGON
                    geometry_filter, sr=feature_layer_wkid),
                return_count_only=True)
            arcpy.AddMessage('count only: ' + str(count))

            feature_set_df = feature_set.sdf
            feature_set_df['Shape'] = feature_set_df['SHAPE'].apply(lambda x: x.as_arcpy)
            feature_set_df = feature_set_df.replace({np.nan: None})

            feature_set_df.apply(lambda x: insert_cursor.insertRow(x[['Shape']]), axis=1)
