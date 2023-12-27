"""
Script documentation

- Tool parameters are accessed using arcpy.GetParameter() or 
                                     arcpy.GetParameterAsText()
- Update derived parameter values using arcpy.SetParameter() or
                                        arcpy.SetParameterAsText()
"""
import arcpy
import pandas as pd
from lib.utils import arcgis_table_to_df

if __name__ == '__main__':

    censoManzanas   = arcpy.GetParameter(0)
    manzanas        = arcpy.GetParameter(1)
    zonifica        = arcpy.GetParameter(2)
    codigoMZ        = arcpy.GetParameter(3)
    datosOD         = arcpy.GetParameter(4)
    zonificaCensos  = arcpy.GetParameter(6)
    denue           = arcpy.GetParameter(7)
    codigo_act      = arcpy.GetParameter(8)

    arcpy.ImportToolbox(r"C:\Users\Rafael\OneDrive - ITESO\2023.3 Otoño\PAP\MyProject\papMovilidad.atbx")

    #! OD
    arcpy.AddMessage('Starting OD')

    # Aquí creamos la agrupación de datos
    arcpy.papMovilidad.JoinDataOD(
        od                  = datosOD,
        Encuesta_Agrupada   = 'in_memory/datosAgrupados'
    )

    # Añadimos los datos de OD al SHP de Zonificación
    arcpy.management.AddJoin(
        in_layer_or_view    = zonifica,
        in_field            = codigoMZ,
        join_table          = 'in_memory/datosAgrupados',
        join_field          = "Ubicación",
        join_type           = "KEEP_ALL",
        index_join_fields   = "NO_INDEX_JOIN_FIELDS"
    )

    # Exportamos los datos
    arcpy.conversion.ExportFeatures(
        in_features             = zonifica,
        out_features            = 'in_memory/zonificaOD',
        where_clause            = "",
        use_field_alias_as_name = "NOT_USE_ALIAS",
        sort_field              = None
    )

    #! DENUE
    arcpy.AddMessage('Starting DENUE')

    # Summarize DENUE
    arcpy.analysis.SummarizeWithin(
        in_polygons         = 'in_memory/zonificaOD',
        in_sum_features     = denue,
        out_feature_class   = 'in_memory/zonificaSW',
        keep_all_polygons   = "KEEP_ALL",
        sum_fields          = None,
        sum_shape           = "ADD_SHAPE_SUM",
        shape_unit          = "SQUAREKILOMETERS",
        group_field         = codigo_act,
        add_min_maj         = "NO_MIN_MAJ",
        add_group_percent   = "NO_PERCENT",
        out_group_table     = 'in_memory/codigo_act_Summary'
    )

    # Create Pivot Table of Acts
    tmpTable = arcgis_table_to_df('in_memory/codigo_act_Summary')
    tmpTable = tmpTable.pivot_table(values = 'Point_Count', index = 'Join_ID', columns = 'codigo_act', aggfunc='sum', fill_value = 0).add_prefix('act_')

    tmpArray = tmpTable.to_records(index = True)
    arcpy.da.NumPyArrayToTable(tmpArray, 'in_memory/tmpTableCrated')

    arcpy.management.MakeFeatureLayer(
        in_features = 'in_memory/zonificaSW',
        out_layer   = 'in_memory/zonificaFeature'
    )


    # TODO: Make this work
    
    # Añadimos los datos de DENUE a Zonificación
    arcpy.management.AddJoin(
        in_layer_or_view    = 'in_memory/zonificaFeature',
        in_field            = 'JOIN ID',
        join_table          = 'in_memory/tmpTableCrated',
        join_field          = "Join_ID",
        join_type           = "KEEP_ALL",
        index_join_fields   = "NO_INDEX_JOIN_FIELDS"
    )
    

    #! CENSO
    arcpy.AddMessage('Starting Censo')

    # Aquí obtenemos el censo por manzanas
    arcpy.papMovilidad.CensoManzanas(
        Censo_Manzanas          = censoManzanas,
        Manzanas_SHP            = manzanas,
        Zonificacion            = zonifica,
        Censo_Manzanas_Shape    = 'in_memory/CensoSHP'
    )

    # Realizamos el spatial join
    arcpy.analysis.SpatialJoin(
        target_features     = 'in_memory/zonificaFeature',
        join_features       = 'in_memory/CensoSHP',
        out_feature_class   = 'in_memory/zonificaCenso',
        join_operation      = "JOIN_ONE_TO_MANY",
        join_type           = "KEEP_ALL",
        match_option        = "INTERSECT",
        search_radius       = None,
        distance_field_name = ""
    )

    #? Close Procedure
    arcpy.AddMessage('Deleting Intermediate Data')
    # Borramos los datos intermedios
    arcpy.management.Delete(r"'in_memory/CensoSHP';'in_memory/zonificaOD';'in_memory/datosAgrupados';")

    # Exportamos los datos
    arcpy.conversion.ExportFeatures(
        in_features             = 'in_memory/zonificaCenso',
        out_features            = zonificaCensos,
        where_clause            = "",
        use_field_alias_as_name = "NOT_USE_ALIAS",
        sort_field              = None
    )
