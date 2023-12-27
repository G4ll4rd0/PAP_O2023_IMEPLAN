"""
Script documentation

- Tool parameters are accessed using arcpy.GetParameter() or 
                                    arcpy.GetParameterAsText()
- Update derived parameter values using arcpy.SetParameter() or
                                        arcpy.SetParameterAsText()
"""
import arcpy
import zipfile
import pandas as pd
from lib.utils import arcgis_table_to_df

if __name__ == '__main__':

    #? INEGI
    censoManzanas   = arcpy.GetParameter(0)
    manzanas        = arcpy.GetParameter(1)
    denue           = arcpy.GetParameter(7)
    codigo_act      = arcpy.GetParameter(8)
    
    #? Zonificacion
    zonifica        = arcpy.GetParameter(2)
    zonificaTxt     = arcpy.GetParameterAsText(2)
    codigoMZ        = arcpy.GetParameter(3)
    codigoMZTxt     = arcpy.GetParameterAsText(3)

    zonificaCode    = zonificaTxt + '_' + codigoMZTxt

    #? OD
    datosOD         = arcpy.GetParameter(4)

    #? MiBici
    estaciones      = arcpy.GetParameter(9)
    xField          = arcpy.GetParameter(12)
    yField          = arcpy.GetParameter(13)
    coordinateSys   = arcpy.GetParameter(14)

    #? GTFS
    gtfs            = arcpy.GetParameterAsText(15)
    coordinateSys2  = arcpy.GetParameter(16)

    #? Outputs
    finalLayer      = arcpy.GetParameter(6)
    tmpFolder       = arcpy.GetParameter(10)
    tmpFoldertxt    = arcpy.GetParameterAsText(10)
    tmpBool         = arcpy.GetParameter(11)


    #! Tmp Data Storage
    arcpy.AddMessage(f'Creating tmpDatabase')

    tmpGDB = 'tmpGeoDB.gdb'
    arcpy.management.CreateFileGDB(
        out_folder_path = tmpFolder,
        out_name        = tmpGDB,
        out_version     = "CURRENT"
    )
    tmpDataPath = tmpFoldertxt + '\\' + tmpGDB
    arcpy.AddMessage(rf'Created: {tmpDataPath}')
    # Ponemos la geodatabase temporal como espacio para guardar los datos del script
    arcpy.env.workspace = tmpDataPath

    arcpy.ImportToolbox(r"C:\Users\Rafael\OneDrive - ITESO\2023.3 Otoño\PAP\MyProject\papMovilidad.atbx")

    #! OD
    arcpy.AddMessage('Starting OD')

    # Aquí creamos la agrupación de datos
    arcpy.papMovilidad.JoinDataOD(
        od                  = datosOD,
        Encuesta_Agrupada   = 'datosAgrupados'
    )

    # Añadimos los datos de OD al SHP de Zonificación
    arcpy.management.AddJoin(
        in_layer_or_view    = zonifica,
        in_field            = codigoMZ,
        join_table          = 'datosAgrupados',
        join_field          = "Ubicación",
        join_type           = "KEEP_ALL",
        index_join_fields   = "NO_INDEX_JOIN_FIELDS"
    )

    #! DENUE
    arcpy.AddMessage('Starting DENUE')

    # Summarize DENUE
    arcpy.analysis.SummarizeWithin(
        in_polygons         = zonifica,
        in_sum_features     = denue,
        out_feature_class   = 'zonificaSW',
        keep_all_polygons   = "KEEP_ALL",
        sum_fields          = None,
        sum_shape           = "ADD_SHAPE_SUM",
        shape_unit          = "SQUAREKILOMETERS",
        group_field         = codigo_act,
        add_min_maj         = "NO_MIN_MAJ",
        add_group_percent   = "NO_PERCENT",
        out_group_table     = 'codigo_act_Summary'
    )

    # Create Pivot Table of Acts
    tmpTable = arcgis_table_to_df('codigo_act_Summary')
    tmpTable = tmpTable.pivot_table(values = 'Point_Count', index = 'Join_ID', columns = 'codigo_act', aggfunc='sum', fill_value = 0).add_prefix('act_')

    tmpArray = tmpTable.to_records(index = True)
    arcpy.da.NumPyArrayToTable(tmpArray, f'{tmpDataPath}\\tmpTableCrated')

    # Renombramos la columna
    arcpy.management.AlterField(
        in_table            = 'zonificaSW',
        field               = "Point_Count",
        new_field_name      = "Unidades_Economicas",
        new_field_alias     = "Unidades_Economicas",
        field_type          = "LONG",
        field_length        = 4,
        field_is_nullable   = "NULLABLE",
        clear_field_alias   = "DO_NOT_CLEAR"
    )

    arcpy.conversion.ExportTable(
        in_table    = 'zonificaSW',
        out_table   = 'joinTable'
    )

    # Añadimos los datos de DENUE a Zonificación
    arcpy.management.JoinField(
        in_data     = "zonificaSW",
        in_field    = "Join_ID",
        join_table  = "tmpTableCrated",
        join_field  = "Join_ID"
    )

    arcpy.conversion.ExportFeatures(
        in_features     = 'zonificaSW',
        out_features    = 'zonificaDEN',
    )

    #! MiBici
    arcpy.AddMessage('Starting MiBici')

    # Ploteamos los puntos de MiBici
    arcpy.management.XYTableToPoint(
        in_table            = estaciones,
        out_feature_class   = 'estacionesmibici_XYTableToPoint',
        x_field             = xField,
        y_field             = yField
    )

    arcpy.AddMessage('  Select')
    # Seleccionamos solo las estaciones activas
    arcpy.management.SelectLayerByAttribute(
        in_layer_or_view    = "estacionesmibici_XYTableToPoint",
        selection_type      = "NEW_SELECTION",
        where_clause        = "status = 'IN_SERVICE'",
        invert_where_clause = None
    )

    arcpy.AddMessage('  Summarize')
    # Sacamos cuantas estaciones activas hay por zona
    arcpy.analysis.SummarizeWithin(
        in_polygons         = zonifica,
        in_sum_features     = "estacionesmibici_XYTableToPoint",
        out_feature_class   = 'zonificacionMiBici',
        keep_all_polygons   = "KEEP_ALL",
        sum_fields          = None,
        sum_shape           = "ADD_SHAPE_SUM",
        shape_unit          = "SQUAREKILOMETERS",
        group_field         = None,
        add_min_maj         = "NO_MIN_MAJ",
        add_group_percent   = "NO_PERCENT",
        out_group_table     = None
    )

    arcpy.AddMessage('  Export')
    # Exportamos los datos que queremos a otra tabla para poder darles tratamiento
    arcpy.conversion.ExportTable(
        in_table                = 'zonificacionMiBici',
        out_table               = 'zonMB',
        where_clause            = "",
        use_field_alias_as_name = "NOT_USE_ALIAS",
        field_mapping           = 'CODIGO_MZ "CODIGO_MZ" true true false 4 Long 0 0,First,#,Zonificacion_Project_SummarizeWithin,CODIGO_MZ,-1,-1;Point_Count "Count of Points" true true false 4 Long 0 0,First,#,Zonificacion_Project_SummarizeWithin,Point_Count,-1,-1',
        sort_field              = None
    )

    arcpy.AddMessage('  Alter Field')
    # Renombramos la columna
    arcpy.management.AlterField(
        in_table            = 'zonMB',
        field               = "Point_Count",
        new_field_name      = "Estaciones_Mi_Bici",
        new_field_alias     = "Estaciones_Mi_Bici",
        field_type          = "LONG",
        field_length        = 4,
        field_is_nullable   = "NULLABLE",
        clear_field_alias   = "DO_NOT_CLEAR"
    )

    arcpy.AddMessage(f'  Add Join in {zonificaCode}')
    # Añadimos los datos de MiBici a Zonificación
    arcpy.management.JoinField(
        in_data     = 'zonificaDEN',
        in_field    = zonificaCode,
        join_table  = 'zonMB',
        join_field  = codigoMZ
    )

    arcpy.conversion.ExportFeatures(
        in_features     = 'zonificaDEN',
        out_features    = 'zonificaMB',
    )

    #! GTFS
    arcpy.AddMessage('Starting GTFS')

    gtfsLoc = tmpFoldertxt + '\\gtfs'

    # Unzip
    with zipfile.ZipFile(gtfs, 'r') as zip:
        zip.extractall(gtfsLoc)
        
    # Commented here, this should be the correct way to do this, but we are only working with one tipe of stops
    '''
    arcpy.AddMessage('  Creating Feature Dataset')
    arcpy.management.CreateFeatureDataset(
        out_dataset_path    = tmpDataPath,
        out_name            = "gtfs",
        spatial_reference   = None
    )

    arcpy.AddMessage('  Creating Public Transit Data Model')
    arcpy.transit.GTFSToPublicTransitDataModel(
        in_gtfs_folders         = gtfsLoc,
        target_feature_dataset  = tmpDataPath + '\\gtfs',
        interpolate="NO_INTERPOLATE",
        append="NO_APPEND"
    )
    '''

    # Plot
    arcpy.management.XYTableToPoint(
        in_table= gtfsLoc + "\\stops.txt",
        out_feature_class= "shapes_XYTableToPoint",
        x_field="stop_lon",
        y_field="stop_lat"
    )

    # Sacamos cuantas estaciones activas hay por zona
    arcpy.analysis.SummarizeWithin(
        in_polygons         = zonifica,
        in_sum_features     = "shapes_XYTableToPoint",
        out_feature_class   = 'zonificacionCamiones',
        keep_all_polygons   = "KEEP_ALL",
        sum_fields          = None,
        sum_shape           = "ADD_SHAPE_SUM",
        shape_unit          = "SQUAREKILOMETERS",
        group_field         = None,
        add_min_maj         = "NO_MIN_MAJ",
        add_group_percent   = "NO_PERCENT",
        out_group_table     = None
    )

    # Exportamos los datos que queremos a otra tabla para poder darles tratamiento
    arcpy.conversion.ExportTable(
        in_table                = 'zonificacionCamiones',
        out_table               = 'zonEC',
        where_clause            = "",
        use_field_alias_as_name = "NOT_USE_ALIAS",
        field_mapping           = 'CODIGO_MZ "CODIGO_MZ" true true false 4 Long 0 0,First,#,Zonificacion_Project_SummarizeWithin,CODIGO_MZ,-1,-1;Point_Count "Count of Points" true true false 4 Long 0 0,First,#,Zonificacion_Project_SummarizeWithin,Point_Count,-1,-1',
        sort_field              = None
    )

    arcpy.management.AlterField(
        in_table            = "zonEC",
        field               = "Point_Count",
        new_field_name      = "Paradas_Camion",
        new_field_alias     = "Paradas_Camion",
        field_type          = "LONG",
        field_length        = 4,
        field_is_nullable   = "NULLABLE",
        clear_field_alias   = "DO_NOT_CLEAR"
    )

    arcpy.management.JoinField(
        in_data     = 'zonificaMB',
        in_field    = zonificaCode,
        join_table  = 'zonEC',
        join_field  = codigoMZ
    )

    arcpy.conversion.ExportFeatures(
        in_features     = 'zonificaMB',
        out_features    = 'zonificaPC',
    )

    #! CENSO
    arcpy.AddMessage('Starting Censo')

    # Aquí obtenemos el censo por manzanas
    arcpy.papMovilidad.CensoManzanas(
        Censo_Manzanas          = censoManzanas,
        Manzanas_SHP            = manzanas,
        Zonificacion            = zonifica,
        Censo_Manzanas_Shape    = 'CensoSHP'
    )

    # Primero se debe realizar un feature to piont, para no meternos en problemas con la unidad de area modificable
    arcpy.management.FeatureToPoint(
        in_features         = "CensoSHP",
        out_feature_class   = 'CensoSHP_Points',
        point_location      = "INSIDE"
    )

    # TODO: Refinar esto para no tener campos duplicados
    arcpy.analysis.SummarizeWithin(
        in_polygons         = zonifica,
        in_sum_features     = "CensoSHP_Points",
        out_feature_class   = 'censoZonificacion',
        keep_all_polygons   = "KEEP_ALL",
        sum_fields="POBTOT Sum;POBFEM Sum;POBTOT Sum;POBFEM Sum;POBMAS Sum;P_0A2 Sum;P_0A2_F Sum;P_0A2_M Sum;P_3YMAS Sum;P_3YMAS_F Sum;P_3YMAS_M Sum;P_5YMAS Sum;P_5YMAS_F Sum;P_5YMAS_M Sum;P_12YMAS Sum;P_12YMAS_F Sum;P_12YMAS_M Sum;P_15YMAS Sum;P_15YMAS_F Sum;P_15YMAS_M Sum;P_18YMAS Sum;P_18YMAS_F Sum;P_18YMAS_M Sum;P_3A5 Sum;P_3A5_F Sum;P_3A5_M Sum;P_6A11 Sum;P_6A11_F Sum;P_6A11_M Sum;P_8A14 Sum;P_8A14_F Sum;P_8A14_M Sum;P_12A14 Sum;P_12A14_F Sum;P_12A14_M Sum;P_15A17 Sum;P_15A17_F Sum;P_15A17_M Sum;P_18A24 Sum;P_18A24_F Sum;P_18A24_M Sum;P_15A49_F Sum;P_60YMAS Sum;P_60YMAS_F Sum;P_60YMAS_M Sum;POB0_14 Sum;POB15_64 Sum;POB65_MAS Sum;PROM_HNV Mean;PNACENT Sum;PNACENT_F Sum;PNACENT_M Sum;PNACOE Sum;PNACOE_F Sum;PNACOE_M Sum;PRES2015 Sum;PRES2015_F Sum;PRES2015_M Sum;PRESOE15 Sum;PRESOE15_F Sum;PRESOE15_M Sum;P3YM_HLI Sum;P3YM_HLI_F Sum;P3YM_HLI_M Sum;P3HLINHE Sum;P3HLINHE_F Sum;P3HLINHE_M Sum;P3HLI_HE Sum;P3HLI_HE_F Sum;P3HLI_HE_M Sum;P5_HLI Sum;P5_HLI_NHE Sum;P5_HLI_HE Sum;PHOG_IND Sum;POB_AFRO Sum;POB_AFRO_F Sum;POB_AFRO_M Sum;PCON_DISC Sum;PCDISC_MOT Sum;PCDISC_VIS Sum;PCDISC_LENG Sum;PCDISC_AUD Sum;PCDISC_MOT2 Sum;PCDISC_MEN Sum;PCON_LIMI Sum;PCLIM_CSB Sum;PCLIM_VIS Sum;PCLIM_HACO Sum;PCLIM_OAUD Sum;PCLIM_MOT2 Sum;PCLIM_RE_CO Sum;PCLIM_PMEN Sum;PSIND_LIM Sum;P3A5_NOA Sum;P3A5_NOA_F Sum;P3A5_NOA_M Sum;P6A11_NOA Sum;P6A11_NOAF Sum;P6A11_NOAM Sum;P12A14NOA Sum;P12A14NOAF Sum;P12A14NOAM Sum;P15A17A Sum;P15A17A_F Sum;P15A17A_M Sum;P18A24A Sum;P18A24A_F Sum;P18A24A_M Sum;P8A14AN Sum;P8A14AN_F Sum;P8A14AN_M Sum;P15YM_AN Sum;P15YM_AN_F Sum;P15YM_AN_M Sum;P15YM_SE Sum;P15YM_SE_F Sum;P15YM_SE_M Sum;P15PRI_IN Sum;P15PRI_INF Sum;P15PRI_INM Sum;P15PRI_CO Sum;P15PRI_COF Sum;P15PRI_COM Sum;P15SEC_IN Sum;P15SEC_INF Sum;P15SEC_INM Sum;P15SEC_CO Sum;P15SEC_COF Sum;P15SEC_COM Sum;P18YM_PB Sum;P18YM_PB_F Sum;P18YM_PB_M Sum;GRAPROES Mean;GRAPROES_F Mean;GRAPROES_M Mean;PEA Sum;PEA_F Sum;PEA_M Sum;PE_INAC Sum;PE_INAC_F Sum;PE_INAC_M Sum;POCUPADA Sum;POCUPADA_F Sum;POCUPADA_M Sum;PDESOCUP Sum;PDESOCUP_F Sum;PDESOCUP_M Sum;PSINDER Sum;PDER_SS Sum;PDER_IMSS Sum;PDER_ISTE Sum;PDER_ISTEE Sum;PAFIL_PDOM Sum;PDER_SEGP Sum;PDER_IMSSB Sum;PAFIL_IPRIV Sum;PAFIL_OTRAI Sum;P12YM_SOLT Sum;P12YM_CASA Sum;P12YM_SEPA Sum;PCATOLICA Sum;PRO_CRIEVA Sum;POTRAS_REL Sum;PSIN_RELIG Sum;TOTHOG Sum;HOGJEF_F Sum;HOGJEF_M Sum;POBHOG Sum;PHOGJEF_F Sum;PHOGJEF_M Sum;VIVTOT Sum;TVIVHAB Sum;TVIVPAR Sum;VIVPAR_HAB Sum;VIVPARH_CV Sum;TVIVPARHAB Sum;VIVPAR_DES Sum;VIVPAR_UT Sum;OCUPVIVPAR Sum;PROM_OCUP Mean;PRO_OCUP_C Mean;VPH_PISODT Sum;VPH_PISOTI Sum;VPH_1DOR Sum;VPH_2YMASD Sum;VPH_1CUART Sum;VPH_2CUART Sum;VPH_3YMASC Sum;VPH_C_ELEC Sum;VPH_S_ELEC Sum;VPH_AGUADV Sum;VPH_AEASP Sum;VPH_AGUAFV Sum;VPH_TINACO Sum;VPH_CISTER Sum;VPH_EXCSA Sum;VPH_LETR Sum;VPH_DRENAJ Sum;VPH_NODREN Sum;VPH_C_SERV Sum;VPH_NDEAED Sum;VPH_DSADMA Sum;VPH_NDACMM Sum;VPH_SNBIEN Sum;VPH_REFRI Sum;VPH_LAVAD Sum;VPH_HMICRO Sum;VPH_AUTOM Sum;VPH_MOTO Sum;VPH_BICI Sum;VPH_RADIO Sum;VPH_TV Sum;VPH_PC Sum;VPH_TELEF Sum;VPH_CEL Sum;VPH_INTER Sum;VPH_STVP Sum;VPH_SPMVPI Sum;VPH_CVJ Sum;VPH_SINRTV Sum;VPH_SINLTC Sum;VPH_SINCINT Sum;VPH_SINTIC Sum",
        sum_shape           = "ADD_SHAPE_SUM",
        shape_unit          = "SQUAREKILOMETERS",
        group_field         = None,
        add_min_maj         = "NO_MIN_MAJ",
        add_group_percent   = "NO_PERCENT",
        out_group_table     = None
    )

    # Export Table
    arcpy.conversion.ExportTable(
        in_table="censoZonificacion",
        out_table='zonificaCenso',
        where_clause="",
        use_field_alias_as_name="NOT_USE_ALIAS",
        field_mapping='CODIGO_MZ "CODIGO_MZ" true true false 4 Long 0 0,First,#,Zonificacion_SummarizeWithin4,CODIGO_MZ,-1,-1;sum_POBTOT "Sum POBTOT" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_POBTOT,-1,-1;sum_POBFEM "Sum POBFEM" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_POBFEM,-1,-1;sum_POBMAS "Sum POBMAS" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_POBMAS,-1,-1;sum_P_0A2 "Sum P_0A2" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_0A2,-1,-1;sum_P_0A2_F "Sum P_0A2_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_0A2_F,-1,-1;sum_P_0A2_M "Sum P_0A2_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_0A2_M,-1,-1;sum_P_3YMAS "Sum P_3YMAS" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_3YMAS,-1,-1;sum_P_3YMAS_F "Sum P_3YMAS_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_3YMAS_F,-1,-1;sum_P_3YMAS_M "Sum P_3YMAS_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_3YMAS_M,-1,-1;sum_P_5YMAS "Sum P_5YMAS" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_5YMAS,-1,-1;sum_P_5YMAS_F "Sum P_5YMAS_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_5YMAS_F,-1,-1;sum_P_5YMAS_M "Sum P_5YMAS_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_5YMAS_M,-1,-1;sum_P_12YMAS "Sum P_12YMAS" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_12YMAS,-1,-1;sum_P_12YMAS_F "Sum P_12YMAS_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_12YMAS_F,-1,-1;sum_P_12YMAS_M "Sum P_12YMAS_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_12YMAS_M,-1,-1;sum_P_15YMAS "Sum P_15YMAS" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_15YMAS,-1,-1;sum_P_15YMAS_F "Sum P_15YMAS_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_15YMAS_F,-1,-1;sum_P_15YMAS_M "Sum P_15YMAS_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_15YMAS_M,-1,-1;sum_P_18YMAS "Sum P_18YMAS" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_18YMAS,-1,-1;sum_P_18YMAS_F "Sum P_18YMAS_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_18YMAS_F,-1,-1;sum_P_18YMAS_M "Sum P_18YMAS_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_18YMAS_M,-1,-1;sum_P_3A5 "Sum P_3A5" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_3A5,-1,-1;sum_P_3A5_F "Sum P_3A5_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_3A5_F,-1,-1;sum_P_3A5_M "Sum P_3A5_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_3A5_M,-1,-1;sum_P_6A11 "Sum P_6A11" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_6A11,-1,-1;sum_P_6A11_F "Sum P_6A11_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_6A11_F,-1,-1;sum_P_6A11_M "Sum P_6A11_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_6A11_M,-1,-1;sum_P_8A14 "Sum P_8A14" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_8A14,-1,-1;sum_P_8A14_F "Sum P_8A14_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_8A14_F,-1,-1;sum_P_8A14_M "Sum P_8A14_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_8A14_M,-1,-1;sum_P_12A14 "Sum P_12A14" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_12A14,-1,-1;sum_P_12A14_F "Sum P_12A14_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_12A14_F,-1,-1;sum_P_12A14_M "Sum P_12A14_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_12A14_M,-1,-1;sum_P_15A17 "Sum P_15A17" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_15A17,-1,-1;sum_P_15A17_F "Sum P_15A17_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_15A17_F,-1,-1;sum_P_15A17_M "Sum P_15A17_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_15A17_M,-1,-1;sum_P_18A24 "Sum P_18A24" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_18A24,-1,-1;sum_P_18A24_F "Sum P_18A24_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_18A24_F,-1,-1;sum_P_18A24_M "Sum P_18A24_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_18A24_M,-1,-1;sum_P_15A49_F "Sum P_15A49_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_15A49_F,-1,-1;sum_P_60YMAS "Sum P_60YMAS" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_60YMAS,-1,-1;sum_P_60YMAS_F "Sum P_60YMAS_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_60YMAS_F,-1,-1;sum_P_60YMAS_M "Sum P_60YMAS_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P_60YMAS_M,-1,-1;sum_POB0_14 "Sum POB0_14" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_POB0_14,-1,-1;sum_POB15_64 "Sum POB15_64" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_POB15_64,-1,-1;sum_POB65_MAS "Sum POB65_MAS" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_POB65_MAS,-1,-1;mean_PROM_HNV "Mean PROM_HNV" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,mean_PROM_HNV,-1,-1;sum_PNACENT "Sum PNACENT" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PNACENT,-1,-1;sum_PNACENT_F "Sum PNACENT_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PNACENT_F,-1,-1;sum_PNACENT_M "Sum PNACENT_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PNACENT_M,-1,-1;sum_PNACOE "Sum PNACOE" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PNACOE,-1,-1;sum_PNACOE_F "Sum PNACOE_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PNACOE_F,-1,-1;sum_PNACOE_M "Sum PNACOE_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PNACOE_M,-1,-1;sum_PRES2015 "Sum PRES2015" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PRES2015,-1,-1;sum_PRES2015_F "Sum PRES2015_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PRES2015_F,-1,-1;sum_PRES2015_M "Sum PRES2015_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PRES2015_M,-1,-1;sum_PRESOE15 "Sum PRESOE15" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PRESOE15,-1,-1;sum_PRESOE15_F "Sum PRESOE15_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PRESOE15_F,-1,-1;sum_PRESOE15_M "Sum PRESOE15_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PRESOE15_M,-1,-1;sum_P3YM_HLI "Sum P3YM_HLI" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P3YM_HLI,-1,-1;sum_P3YM_HLI_F "Sum P3YM_HLI_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P3YM_HLI_F,-1,-1;sum_P3YM_HLI_M "Sum P3YM_HLI_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P3YM_HLI_M,-1,-1;sum_P3HLINHE "Sum P3HLINHE" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P3HLINHE,-1,-1;sum_P3HLINHE_F "Sum P3HLINHE_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P3HLINHE_F,-1,-1;sum_P3HLINHE_M "Sum P3HLINHE_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P3HLINHE_M,-1,-1;sum_P3HLI_HE "Sum P3HLI_HE" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P3HLI_HE,-1,-1;sum_P3HLI_HE_F "Sum P3HLI_HE_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P3HLI_HE_F,-1,-1;sum_P3HLI_HE_M "Sum P3HLI_HE_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P3HLI_HE_M,-1,-1;sum_P5_HLI "Sum P5_HLI" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P5_HLI,-1,-1;sum_P5_HLI_NHE "Sum P5_HLI_NHE" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P5_HLI_NHE,-1,-1;sum_P5_HLI_HE "Sum P5_HLI_HE" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P5_HLI_HE,-1,-1;sum_PHOG_IND "Sum PHOG_IND" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PHOG_IND,-1,-1;sum_POB_AFRO "Sum POB_AFRO" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_POB_AFRO,-1,-1;sum_POB_AFRO_F "Sum POB_AFRO_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_POB_AFRO_F,-1,-1;sum_POB_AFRO_M "Sum POB_AFRO_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_POB_AFRO_M,-1,-1;sum_PCON_DISC "Sum PCON_DISC" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PCON_DISC,-1,-1;sum_PCDISC_MOT "Sum PCDISC_MOT" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PCDISC_MOT,-1,-1;sum_PCDISC_VIS "Sum PCDISC_VIS" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PCDISC_VIS,-1,-1;sum_PCDISC_LENG "Sum PCDISC_LENG" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PCDISC_LENG,-1,-1;sum_PCDISC_AUD "Sum PCDISC_AUD" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PCDISC_AUD,-1,-1;sum_PCDISC_MOT2 "Sum PCDISC_MOT2" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PCDISC_MOT2,-1,-1;sum_PCDISC_MEN "Sum PCDISC_MEN" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PCDISC_MEN,-1,-1;sum_PCON_LIMI "Sum PCON_LIMI" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PCON_LIMI,-1,-1;sum_PCLIM_CSB "Sum PCLIM_CSB" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PCLIM_CSB,-1,-1;sum_PCLIM_VIS "Sum PCLIM_VIS" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PCLIM_VIS,-1,-1;sum_PCLIM_HACO "Sum PCLIM_HACO" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PCLIM_HACO,-1,-1;sum_PCLIM_OAUD "Sum PCLIM_OAUD" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PCLIM_OAUD,-1,-1;sum_PCLIM_MOT2 "Sum PCLIM_MOT2" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PCLIM_MOT2,-1,-1;sum_PCLIM_RE_CO "Sum PCLIM_RE_CO" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PCLIM_RE_CO,-1,-1;sum_PCLIM_PMEN "Sum PCLIM_PMEN" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PCLIM_PMEN,-1,-1;sum_PSIND_LIM "Sum PSIND_LIM" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PSIND_LIM,-1,-1;sum_P3A5_NOA "Sum P3A5_NOA" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P3A5_NOA,-1,-1;sum_P3A5_NOA_F "Sum P3A5_NOA_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P3A5_NOA_F,-1,-1;sum_P3A5_NOA_M "Sum P3A5_NOA_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P3A5_NOA_M,-1,-1;sum_P6A11_NOA "Sum P6A11_NOA" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P6A11_NOA,-1,-1;sum_P6A11_NOAF "Sum P6A11_NOAF" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P6A11_NOAF,-1,-1;sum_P6A11_NOAM "Sum P6A11_NOAM" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P6A11_NOAM,-1,-1;sum_P12A14NOA "Sum P12A14NOA" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P12A14NOA,-1,-1;sum_P12A14NOAF "Sum P12A14NOAF" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P12A14NOAF,-1,-1;sum_P12A14NOAM "Sum P12A14NOAM" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P12A14NOAM,-1,-1;sum_P15A17A "Sum P15A17A" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15A17A,-1,-1;sum_P15A17A_F "Sum P15A17A_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15A17A_F,-1,-1;sum_P15A17A_M "Sum P15A17A_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15A17A_M,-1,-1;sum_P18A24A "Sum P18A24A" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P18A24A,-1,-1;sum_P18A24A_F "Sum P18A24A_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P18A24A_F,-1,-1;sum_P18A24A_M "Sum P18A24A_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P18A24A_M,-1,-1;sum_P8A14AN "Sum P8A14AN" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P8A14AN,-1,-1;sum_P8A14AN_F "Sum P8A14AN_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P8A14AN_F,-1,-1;sum_P8A14AN_M "Sum P8A14AN_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P8A14AN_M,-1,-1;sum_P15YM_AN "Sum P15YM_AN" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15YM_AN,-1,-1;sum_P15YM_AN_F "Sum P15YM_AN_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15YM_AN_F,-1,-1;sum_P15YM_AN_M "Sum P15YM_AN_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15YM_AN_M,-1,-1;sum_P15YM_SE "Sum P15YM_SE" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15YM_SE,-1,-1;sum_P15YM_SE_F "Sum P15YM_SE_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15YM_SE_F,-1,-1;sum_P15YM_SE_M "Sum P15YM_SE_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15YM_SE_M,-1,-1;sum_P15PRI_IN "Sum P15PRI_IN" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15PRI_IN,-1,-1;sum_P15PRI_INF "Sum P15PRI_INF" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15PRI_INF,-1,-1;sum_P15PRI_INM "Sum P15PRI_INM" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15PRI_INM,-1,-1;sum_P15PRI_CO "Sum P15PRI_CO" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15PRI_CO,-1,-1;sum_P15PRI_COF "Sum P15PRI_COF" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15PRI_COF,-1,-1;sum_P15PRI_COM "Sum P15PRI_COM" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15PRI_COM,-1,-1;sum_P15SEC_IN "Sum P15SEC_IN" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15SEC_IN,-1,-1;sum_P15SEC_INF "Sum P15SEC_INF" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15SEC_INF,-1,-1;sum_P15SEC_INM "Sum P15SEC_INM" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15SEC_INM,-1,-1;sum_P15SEC_CO "Sum P15SEC_CO" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15SEC_CO,-1,-1;sum_P15SEC_COF "Sum P15SEC_COF" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15SEC_COF,-1,-1;sum_P15SEC_COM "Sum P15SEC_COM" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P15SEC_COM,-1,-1;sum_P18YM_PB "Sum P18YM_PB" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P18YM_PB,-1,-1;sum_P18YM_PB_F "Sum P18YM_PB_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P18YM_PB_F,-1,-1;sum_P18YM_PB_M "Sum P18YM_PB_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P18YM_PB_M,-1,-1;mean_GRAPROES "Mean GRAPROES" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,mean_GRAPROES,-1,-1;mean_GRAPROES_F "Mean GRAPROES_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,mean_GRAPROES_F,-1,-1;mean_GRAPROES_M "Mean GRAPROES_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,mean_GRAPROES_M,-1,-1;sum_PEA "Sum PEA" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PEA,-1,-1;sum_PEA_F "Sum PEA_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PEA_F,-1,-1;sum_PEA_M "Sum PEA_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PEA_M,-1,-1;sum_PE_INAC "Sum PE_INAC" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PE_INAC,-1,-1;sum_PE_INAC_F "Sum PE_INAC_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PE_INAC_F,-1,-1;sum_PE_INAC_M "Sum PE_INAC_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PE_INAC_M,-1,-1;sum_POCUPADA "Sum POCUPADA" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_POCUPADA,-1,-1;sum_POCUPADA_F "Sum POCUPADA_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_POCUPADA_F,-1,-1;sum_POCUPADA_M "Sum POCUPADA_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_POCUPADA_M,-1,-1;sum_PDESOCUP "Sum PDESOCUP" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PDESOCUP,-1,-1;sum_PDESOCUP_F "Sum PDESOCUP_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PDESOCUP_F,-1,-1;sum_PDESOCUP_M "Sum PDESOCUP_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PDESOCUP_M,-1,-1;sum_PSINDER "Sum PSINDER" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PSINDER,-1,-1;sum_PDER_SS "Sum PDER_SS" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PDER_SS,-1,-1;sum_PDER_IMSS "Sum PDER_IMSS" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PDER_IMSS,-1,-1;sum_PDER_ISTE "Sum PDER_ISTE" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PDER_ISTE,-1,-1;sum_PDER_ISTEE "Sum PDER_ISTEE" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PDER_ISTEE,-1,-1;sum_PAFIL_PDOM "Sum PAFIL_PDOM" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PAFIL_PDOM,-1,-1;sum_PDER_SEGP "Sum PDER_SEGP" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PDER_SEGP,-1,-1;sum_PDER_IMSSB "Sum PDER_IMSSB" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PDER_IMSSB,-1,-1;sum_PAFIL_IPRIV "Sum PAFIL_IPRIV" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PAFIL_IPRIV,-1,-1;sum_PAFIL_OTRAI "Sum PAFIL_OTRAI" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PAFIL_OTRAI,-1,-1;sum_P12YM_SOLT "Sum P12YM_SOLT" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P12YM_SOLT,-1,-1;sum_P12YM_CASA "Sum P12YM_CASA" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P12YM_CASA,-1,-1;sum_P12YM_SEPA "Sum P12YM_SEPA" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_P12YM_SEPA,-1,-1;sum_PCATOLICA "Sum PCATOLICA" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PCATOLICA,-1,-1;sum_PRO_CRIEVA "Sum PRO_CRIEVA" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PRO_CRIEVA,-1,-1;sum_POTRAS_REL "Sum POTRAS_REL" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_POTRAS_REL,-1,-1;sum_PSIN_RELIG "Sum PSIN_RELIG" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PSIN_RELIG,-1,-1;sum_TOTHOG "Sum TOTHOG" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_TOTHOG,-1,-1;sum_HOGJEF_F "Sum HOGJEF_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_HOGJEF_F,-1,-1;sum_HOGJEF_M "Sum HOGJEF_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_HOGJEF_M,-1,-1;sum_POBHOG "Sum POBHOG" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_POBHOG,-1,-1;sum_PHOGJEF_F "Sum PHOGJEF_F" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PHOGJEF_F,-1,-1;sum_PHOGJEF_M "Sum PHOGJEF_M" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_PHOGJEF_M,-1,-1;sum_VIVTOT "Sum VIVTOT" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VIVTOT,-1,-1;sum_TVIVHAB "Sum TVIVHAB" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_TVIVHAB,-1,-1;sum_TVIVPAR "Sum TVIVPAR" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_TVIVPAR,-1,-1;sum_VIVPAR_HAB "Sum VIVPAR_HAB" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VIVPAR_HAB,-1,-1;sum_VIVPARH_CV "Sum VIVPARH_CV" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VIVPARH_CV,-1,-1;sum_TVIVPARHAB "Sum TVIVPARHAB" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_TVIVPARHAB,-1,-1;sum_VIVPAR_DES "Sum VIVPAR_DES" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VIVPAR_DES,-1,-1;sum_VIVPAR_UT "Sum VIVPAR_UT" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VIVPAR_UT,-1,-1;sum_OCUPVIVPAR "Sum OCUPVIVPAR" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_OCUPVIVPAR,-1,-1;mean_PROM_OCUP "Mean PROM_OCUP" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,mean_PROM_OCUP,-1,-1;mean_PRO_OCUP_C "Mean PRO_OCUP_C" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,mean_PRO_OCUP_C,-1,-1;sum_VPH_PISODT "Sum VPH_PISODT" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_PISODT,-1,-1;sum_VPH_PISOTI "Sum VPH_PISOTI" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_PISOTI,-1,-1;sum_VPH_1DOR "Sum VPH_1DOR" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_1DOR,-1,-1;sum_VPH_2YMASD "Sum VPH_2YMASD" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_2YMASD,-1,-1;sum_VPH_1CUART "Sum VPH_1CUART" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_1CUART,-1,-1;sum_VPH_2CUART "Sum VPH_2CUART" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_2CUART,-1,-1;sum_VPH_3YMASC "Sum VPH_3YMASC" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_3YMASC,-1,-1;sum_VPH_C_ELEC "Sum VPH_C_ELEC" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_C_ELEC,-1,-1;sum_VPH_S_ELEC "Sum VPH_S_ELEC" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_S_ELEC,-1,-1;sum_VPH_AGUADV "Sum VPH_AGUADV" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_AGUADV,-1,-1;sum_VPH_AEASP "Sum VPH_AEASP" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_AEASP,-1,-1;sum_VPH_AGUAFV "Sum VPH_AGUAFV" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_AGUAFV,-1,-1;sum_VPH_TINACO "Sum VPH_TINACO" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_TINACO,-1,-1;sum_VPH_CISTER "Sum VPH_CISTER" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_CISTER,-1,-1;sum_VPH_EXCSA "Sum VPH_EXCSA" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_EXCSA,-1,-1;sum_VPH_LETR "Sum VPH_LETR" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_LETR,-1,-1;sum_VPH_DRENAJ "Sum VPH_DRENAJ" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_DRENAJ,-1,-1;sum_VPH_NODREN "Sum VPH_NODREN" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_NODREN,-1,-1;sum_VPH_C_SERV "Sum VPH_C_SERV" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_C_SERV,-1,-1;sum_VPH_NDEAED "Sum VPH_NDEAED" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_NDEAED,-1,-1;sum_VPH_DSADMA "Sum VPH_DSADMA" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_DSADMA,-1,-1;sum_VPH_NDACMM "Sum VPH_NDACMM" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_NDACMM,-1,-1;sum_VPH_SNBIEN "Sum VPH_SNBIEN" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_SNBIEN,-1,-1;sum_VPH_REFRI "Sum VPH_REFRI" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_REFRI,-1,-1;sum_VPH_LAVAD "Sum VPH_LAVAD" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_LAVAD,-1,-1;sum_VPH_HMICRO "Sum VPH_HMICRO" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_HMICRO,-1,-1;sum_VPH_AUTOM "Sum VPH_AUTOM" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_AUTOM,-1,-1;sum_VPH_MOTO "Sum VPH_MOTO" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_MOTO,-1,-1;sum_VPH_BICI "Sum VPH_BICI" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_BICI,-1,-1;sum_VPH_RADIO "Sum VPH_RADIO" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_RADIO,-1,-1;sum_VPH_TV "Sum VPH_TV" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_TV,-1,-1;sum_VPH_PC "Sum VPH_PC" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_PC,-1,-1;sum_VPH_TELEF "Sum VPH_TELEF" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_TELEF,-1,-1;sum_VPH_CEL "Sum VPH_CEL" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_CEL,-1,-1;sum_VPH_INTER "Sum VPH_INTER" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_INTER,-1,-1;sum_VPH_STVP "Sum VPH_STVP" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_STVP,-1,-1;sum_VPH_SPMVPI "Sum VPH_SPMVPI" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_SPMVPI,-1,-1;sum_VPH_CVJ "Sum VPH_CVJ" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_CVJ,-1,-1;sum_VPH_SINRTV "Sum VPH_SINRTV" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_SINRTV,-1,-1;sum_VPH_SINLTC "Sum VPH_SINLTC" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_SINLTC,-1,-1;sum_VPH_SINCINT "Sum VPH_SINCINT" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_SINCINT,-1,-1;sum_VPH_SINTIC "Sum VPH_SINTIC" true true false 8 Double 0 0,First,#,Zonificacion_SummarizeWithin4,sum_VPH_SINTIC,-1,-1;Point_Count "Count of Points" true true false 4 Long 0 0,First,#,Zonificacion_SummarizeWithin4,Point_Count,-1,-1',
        sort_field=None
    )

    arcpy.management.AlterField(
        in_table            = "zonificaCenso",
        field               = "Point_Count",
        new_field_name      = "Manzanas",
        new_field_alias     = "Manzanas",
        field_type          = "LONG",
        field_length        = 4,
        field_is_nullable   = "NULLABLE",
        clear_field_alias   = "DO_NOT_CLEAR"
    )

    arcpy.management.JoinField(
        in_data     = 'zonificaPC',
        in_field    = zonificaCode,
        join_table  = 'zonificaCenso',
        join_field  = codigoMZ
    )

    #? Close Procedure
    arcpy.AddMessage('Exporting Final Layer')

    # Exportamos los datos
    arcpy.conversion.ExportFeatures(
        in_features             = 'zonificaPC',
        out_features            = finalLayer,
        where_clause            = "",
        use_field_alias_as_name = "NOT_USE_ALIAS",
        sort_field              = None
    )

    # Borramos los datos intermedios
    if tmpBool:
        arcpy.AddMessage('Keeping Intermediate Data')
    else:
        arcpy.AddMessage('Deleting Intermediate Data')
        arcpy.management.Delete(fr"'{tmpDataPath}';")