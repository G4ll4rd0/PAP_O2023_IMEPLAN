"""
Script documentation

- Tool parameters are accessed using arcpy.GetParameter() or 
                                    arcpy.GetParameterAsText()
- Update derived parameter values using arcpy.SetParameter() or
                                        arcpy.SetParameterAsText()
"""
import time
import json
import arcpy
import pickle
import xgboost
import keplergl
import numpy as np
import pandas as pd
import routingpy as rp
import geopandas as gpd
import tensorflow as tf
from tensorflow.keras import Model
from lib.utils import arcgis_table_to_df
from tensorflow.keras.layers import Input, Dense

DEBUG = False

if __name__ == '__main__':

    #? OD
    datosOD         = arcpy.GetParameter(0)

    #? Full Data
    fData           = arcpy.GetParameter(1)

    #? RoutingPy
    apiKey          = arcpy.GetParameterAsText(2)

    #? Zonificacion
    zonificacion    = arcpy.GetParameter(3)

    #? Outputs
    outTable        = arcpy.GetParameter(4)
    map1Path        = arcpy.GetParameterAsText(5)
    map2Path        = arcpy.GetParameterAsText(6)

    #! OD Estimación
    arcpy.AddMessage('Starting OD')

    odData = arcgis_table_to_df(datosOD)
    odData.dropna(inplace=True)
    odData.set_index(['Origen', 'Destino'], inplace=True)
    # Agrupamos todos los valores de vehículo
    vehiculo = [x for x in odData.columns if 'Auto' in x or 'Camioneta' in x]
    odData.insert(5, 'Vehiculo', odData[vehiculo].sum(axis=1))
    odData.drop(vehiculo, axis = 1, inplace=True)

    #! Generated data
    arcpy.AddMessage('Starting Generated Data')

    arcpy.conversion.ExportTable(
        in_table                = fData,
        out_table               = "in_memory/fullDataTable",
        where_clause            = "",
        use_field_alias_as_name = "NOT_USE_ALIAS",
        sort_field=None
    )

    fullData = arcgis_table_to_df("in_memory/fullDataTable")
    indexes = [x for x in fullData.columns if 'ID' in x or 'Shape' in x or 'Zonificacion' in x or 'Ubicación' in x]
    fullData = fullData.drop(indexes, axis = 1)

    #! Predict Travels
    arcpy.AddMessage('Predicting Travels')

    with open('./model/origen.pkl', 'rb') as f:
        originModel = pickle.load(f)

    with open('./model/destino.pkl', 'rb') as f:
        destinationModel = pickle.load(f)

    # Prediction data
    arcpy.AddMessage('  Creating Prediction Data')

    selectedVars = ['sum_POBTOT', 'act_722515', 'act_722514', 'act_812110', 'Unidades_Economicas','Paradas_Camion','sum_VPH_AUTOM', 'sum_TVIVPARHAB']
    selectedData = fullData[['CODIGO_MZ'] + selectedVars].set_index('CODIGO_MZ').fillna(0)
    selectedData['%VPH_AUTOMOVIL'] = selectedData['sum_VPH_AUTOM']/selectedData['sum_TVIVPARHAB']
    selectedData.drop(columns=['sum_VPH_AUTOM', 'sum_TVIVPARHAB'], inplace=True)
    selectedData.fillna(0, inplace = True)
    toJoin = selectedData.copy()
    toJoin['Viajes Origen'] = originModel.predict(selectedData)
    toJoin['Viajes Destino'] = destinationModel.predict(selectedData)
    toJoin['Viajes Origen'] = np.int64(round(toJoin['Viajes Origen'], 0))
    toJoin['Viajes Destino'] = np.int64(round(toJoin['Viajes Destino'], 0))
    toJoin.drop(selectedData.columns, axis = 1, inplace = True)

    # Joining Data
    joining = fullData.copy()
    joining = joining.join(toJoin)

    odcopy = odData.copy()
    odcopy = odcopy.join(joining, on='Origen')
    odcopy = odcopy.join(joining, on='Destino', rsuffix='__DESTINO', lsuffix='__ORIGEN')

    #! Network data
    arcpy.AddMessage('Starting Network Data')

    ors = rp.routers.ORS(apiKey)

    # zonificacionXY
    arcpy.AddMessage('  Creating XY Data')

    arcpy.management.FeatureToPoint(
        in_features         = zonificacion,
        out_feature_class   = "zonPoint",
        point_location      = "INSIDE"
    )

    arcpy.management.CalculateGeometryAttributes(
        in_features         = "zonPoint",
        geometry_property   = "PX POINT_X;PY POINT_Y;Annot POINT_COORD_NOTATION",
        length_unit         = "",
        area_unit           = "",
        coordinate_system   = 'GEOGCS["GCS_Mexico_ITRF2008",DATUM["D_Mexico_ITRF2008",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]',
        coordinate_format   = "SAME_AS_INPUT"
    )

    arcpy.conversion.ExportTable(
        in_table                = "zonPoint",
        out_table               = "in_memory/zonificacionXY",
        where_clause            = "",
        use_field_alias_as_name = "NOT_USE_ALIAS",
        sort_field              = None
    )

    xy = arcgis_table_to_df("in_memory/zonificacionXY")
    xy = xy.set_index('CODIGO_MZ')
    xy['list'] = xy[['PX', 'PY']].values.tolist()

    arcpy.AddMessage('  Getting Car Data')
    durationData = pd.DataFrame(columns=xy.index, index=xy.index)
    for i in range(0,68):
        dest = [i for i in range(7*i, 7*(i+1))]
        if i == 40:
            arcpy.AddMessage('      Sleeping for 60sec to reset API use')
            time.sleep(60)
            arcpy.AddMessage('      Continuing')
        dist = ors.matrix(xy.list.values.tolist(), profile = 'driving-car', sources=dest)
        durationData.iloc[dest] = np.array(dist.raw['durations'])

    # Se debe correr una vez más para cubrir todos
    dest = [476, 477]
    dist = ors.matrix(xy.list.values.tolist(), profile = 'driving-car', sources=dest)
    durationData.iloc[dest] = np.array(dist.raw['durations'])

    arcpy.AddMessage('  Sleeping for 60sec to reset API use')
    time.sleep(60)
    arcpy.AddMessage('  Continuing')

    arcpy.AddMessage('  Getting Walking Data')
    durationData2 = pd.DataFrame(columns=xy.index, index=xy.index)
    for i in range(0,68):
        dest = [i for i in range(7*i, 7*(i+1))]
        if i == 40: 
            arcpy.AddMessage('      Sleeping for 60sec to reset API use')
            time.sleep(60)
            arcpy.AddMessage('      Continuing')
        dist = ors.matrix(xy.list.values.tolist(), profile = 'foot-walking', sources=dest)
        durationData2.iloc[dest] = np.array(dist.raw['durations'])

    # Se debe correr una vez más para cubrir todos
    dest = [476, 477]
    dist = ors.matrix(xy.list.values.tolist(), profile = 'foot-walking', sources=dest)
    durationData2.iloc[dest] = np.array(dist.raw['durations'])

    # Joining Data
    dD = durationData.reset_index().melt(id_vars='CODIGO_MZ', var_name='Destino', value_name='travel_time').rename(columns={'CODIGO_MZ': 'Origen'}).set_index(['Origen', 'Destino']).sort_index()
    dD2 = durationData2.reset_index().melt(id_vars='CODIGO_MZ', var_name='Destino', value_name='travel_time').rename(columns={'CODIGO_MZ': 'Origen'}).set_index(['Origen', 'Destino']).sort_index()
    travelData = dD.join(dD2, lsuffix='_Driving', rsuffix='_Walking')
    odcopy = odcopy.join(travelData)
    odcopy.fillna(0, inplace=True)

    #! Predicting Travel distribution
    arcpy.AddMessage('Starting Flux Model')

    targets = ['Caminando', 'Transporte_Colectivo', 'Taxi', 'Bicicleta', 'Motocicleta', 'Vehiculo', 'Otros', 'Total']
    categorical = odcopy.select_dtypes(include=['object']).columns
    codes = [x for x in odcopy.columns if 'CODIGO' in x]
    predictors = [x for x in odcopy.columns if x not in targets and x not in categorical and x not in codes]

    if DEBUG:
        arcpy.AddMessage('  Created Cols')

    with open('./model/flux.pkl', 'rb') as f:
        fluxModel = pickle.load(f)

    arcpy.management.Delete('in_memory')

    if DEBUG:
        arcpy.AddMessage('  Opened Model')
        arcpy.AddMessage([x for x in predictors if 'datosAgrupados' not in x and 'act' not in x and 'sum' not in x])

    y_pred = pd.DataFrame(fluxModel.predict(odcopy[predictors]), index=odcopy.index, columns=odcopy[targets].columns)
    y_pred[y_pred < 0] = 0
    y_pred = y_pred.astype(int)

    if DEBUG:
        arcpy.AddMessage('  Predicted')

    tmpArray = y_pred.to_records(index = True)
    arcpy.da.NumPyArrayToTable(tmpArray, 'in_memory/tmpTableCrated')

    if DEBUG:
        arcpy.AddMessage('  ArcGis Table')

    arcpy.conversion.ExportTable(
        in_table                = 'in_memory/tmpTableCrated',
        out_table               = outTable,
        where_clause            = "",
        use_field_alias_as_name = "NOT_USE_ALIAS",
        sort_field              = None
    )

    arcpy.AddMessage('  Exported Table')

    #! Visualizations
    arcpy.AddMessage('Starting Kepler Visualizations')

    # Viajes OD
    arcpy.AddMessage('  OD Prediction')

    #? Zonas to GPD
    arcpy.conversion.FeaturesToJSON(
        in_features     = zonificacion,
        out_json_file   = 'in_memory/zona.geojson',
        format_json     = "NOT_FORMATTED",
        include_z_values= "NO_Z_VALUES",
        include_m_values= "NO_M_VALUES",
        geoJSON         = "GEOJSON",
        outputToWGS84   = "KEEP_INPUT_SR",
        use_field_alias = "USE_FIELD_NAME"
    )

    zonas = gpd.GeoDataFrame.from_file('in_memory/zona.geojson')
    if DEBUG:
        arcpy.AddMessage(zonas[0:10])
    
    toDrop = [x for x in zonas.columns if x not in ['CODIGO_MZ', 'geometry']]
    zonasMod = zonas.drop(toDrop, axis = 1)
    zonasMod = zonasMod.join(toJoin, on='CODIGO_MZ')

    config1 = {'version': 'v1',
 'config': {'visState': {'filters': [],
   'layers': [{'id': 'farkchy',
     'type': 'geojson',
     'config': {'dataId': 'Zonas',
      'label': 'Zonas_Destino',
      'color': [130, 154, 227],
      'highlightColor': [252, 242, 26, 255],
      'columns': {'geojson': 'geometry'},
      'isVisible': True,
      'visConfig': {'opacity': 0.54,
       'strokeOpacity': 0.8,
       'thickness': 0.5,
       'strokeColor': None,
       'colorRange': {'name': 'Uber Viz Diverging 1.5',
        'type': 'diverging',
        'category': 'Uber',
        'colors': ['#00939C',
         '#5DBABF',
         '#BAE1E2',
         '#F8C0AA',
         '#DD7755',
         '#C22E00']},
       'strokeColorRange': {'name': 'Global Warming',
        'type': 'sequential',
        'category': 'Uber',
        'colors': ['#5A1846',
         '#900C3F',
         '#C70039',
         '#E3611C',
         '#F1920E',
         '#FFC300']},
       'radius': 10,
       'sizeRange': [0, 10],
       'radiusRange': [0, 50],
       'heightRange': [0, 500],
       'elevationScale': 5,
       'enableElevationZoomFactor': True,
       'stroked': True,
       'filled': True,
       'enable3d': True,
       'wireframe': False},
      'hidden': False,
      'textLabel': [{'field': None,
        'color': [255, 255, 255],
        'size': 18,
        'offset': [0, 0],
        'anchor': 'start',
        'alignment': 'center'}]},
     'visualChannels': {'colorField': {'name': 'Viajes Destino',
       'type': 'integer'},
      'colorScale': 'quantile',
      'strokeColorField': None,
      'strokeColorScale': 'quantile',
      'sizeField': None,
      'sizeScale': 'linear',
      'heightField': {'name': 'Viajes Destino', 'type': 'integer'},
      'heightScale': 'linear',
      'radiusField': None,
      'radiusScale': 'linear'}},
    {'id': 'rlxa3os',
     'type': 'geojson',
     'config': {'dataId': 'Zonas',
      'label': 'Zonas_Origen',
      'color': [130, 154, 227],
      'highlightColor': [252, 242, 26, 255],
      'columns': {'geojson': 'geometry'},
      'isVisible': True,
      'visConfig': {'opacity': 0.54,
       'strokeOpacity': 0.8,
       'thickness': 0.5,
       'strokeColor': None,
       'colorRange': {'name': 'Uber Viz Diverging 1.5',
        'type': 'diverging',
        'category': 'Uber',
        'colors': ['#00939C',
         '#5DBABF',
         '#BAE1E2',
         '#F8C0AA',
         '#DD7755',
         '#C22E00']},
       'strokeColorRange': {'name': 'Global Warming',
        'type': 'sequential',
        'category': 'Uber',
        'colors': ['#5A1846',
         '#900C3F',
         '#C70039',
         '#E3611C',
         '#F1920E',
         '#FFC300']},
       'radius': 10,
       'sizeRange': [0, 10],
       'radiusRange': [0, 50],
       'heightRange': [0, 500],
       'elevationScale': 5,
       'enableElevationZoomFactor': True,
       'stroked': True,
       'filled': True,
       'enable3d': True,
       'wireframe': False},
      'hidden': False,
      'textLabel': [{'field': None,
        'color': [255, 255, 255],
        'size': 18,
        'offset': [0, 0],
        'anchor': 'start',
        'alignment': 'center'}]},
     'visualChannels': {'colorField': {'name': 'Viajes Origen',
       'type': 'integer'},
      'colorScale': 'quantile',
      'strokeColorField': None,
      'strokeColorScale': 'quantile',
      'sizeField': None,
      'sizeScale': 'linear',
      'heightField': {'name': 'Viajes Origen', 'type': 'integer'},
      'heightScale': 'linear',
      'radiusField': None,
      'radiusScale': 'linear'}}],
   'interactionConfig': {'tooltip': {'fieldsToShow': {'Zonas': [{'name': 'CODIGO_MZ',
        'format': None},
       {'name': 'Viajes Origen', 'format': None},
       {'name': 'Viajes Destino', 'format': None}],
      'Copy of Zonas': [{'name': 'CODIGO_MZ', 'format': None},
       {'name': 'Viajes Origen', 'format': None},
       {'name': 'Viajes Destino', 'format': None}]},
     'compareMode': False,
     'compareType': 'absolute',
     'enabled': True},
    'brush': {'size': 0.5, 'enabled': False},
    'geocoder': {'enabled': False},
    'coordinate': {'enabled': False}},
   'layerBlending': 'normal',
   'splitMaps': [{'layers': {'farkchy': False, 'rlxa3os': True}},
    {'layers': {'farkchy': True, 'rlxa3os': False}}],
   'animationConfig': {'currentTime': None, 'speed': 1}},
  'mapState': {'bearing': 24,
   'dragRotate': True,
   'latitude': 20.55202873488371,
   'longitude': -103.36770186662218,
   'pitch': 50,
   'zoom': 9,
   'isSplit': True},
  'mapStyle': {'styleType': 'dark',
   'topLayerGroups': {},
   'visibleLayerGroups': {'label': True,
    'road': True,
    'border': False,
    'building': True,
    'water': True,
    'land': True,
    '3d building': False},
   'threeDBuildingColor': [9.665468314072013,
    17.18305478057247,
    31.1442867897876],
   'mapStyles': {}}}}
    
    map_clean1 = keplergl.KeplerGl(data={'Zonas': zonasMod, 'Copy of Zonas': zonasMod}, config = config1)
    map_clean1.save_to_html(file_name=map1Path)

    # Flux Distribution
    arcpy.AddMessage('  Distribution')
    fluxData = y_pred.join(xy, 'Origen').join(xy, 'Destino', lsuffix='_Origen', rsuffix='_Destino')

    config2 = {'version': 'v1',
 'config': {'visState': {'filters': [],
   'layers': [{'id': '2um4',
     'type': 'geojson',
     'config': {'dataId': 'Zonas',
      'label': 'Zonas',
      'color': [248, 149, 112],
      'highlightColor': [252, 242, 26, 255],
      'columns': {'geojson': 'geometry'},
      'isVisible': True,
      'visConfig': {'opacity': 0.8,
       'strokeOpacity': 0.8,
       'thickness': 0.5,
       'strokeColor': [130, 154, 227],
       'colorRange': {'name': 'Global Warming',
        'type': 'sequential',
        'category': 'Uber',
        'colors': ['#5A1846',
         '#900C3F',
         '#C70039',
         '#E3611C',
         '#F1920E',
         '#FFC300']},
       'strokeColorRange': {'name': 'Global Warming',
        'type': 'sequential',
        'category': 'Uber',
        'colors': ['#5A1846',
         '#900C3F',
         '#C70039',
         '#E3611C',
         '#F1920E',
         '#FFC300']},
       'radius': 10,
       'sizeRange': [0, 10],
       'radiusRange': [0, 50],
       'heightRange': [0, 500],
       'elevationScale': 5,
       'enableElevationZoomFactor': True,
       'stroked': True,
       'filled': False,
       'enable3d': False,
       'wireframe': False},
      'hidden': False,
      'textLabel': [{'field': None,
        'color': [255, 255, 255],
        'size': 18,
        'offset': [0, 0],
        'anchor': 'start',
        'alignment': 'center'}]},
     'visualChannels': {'colorField': None,
      'colorScale': 'quantile',
      'strokeColorField': None,
      'strokeColorScale': 'quantile',
      'sizeField': None,
      'sizeScale': 'linear',
      'heightField': None,
      'heightScale': 'linear',
      'radiusField': None,
      'radiusScale': 'linear'}},
    {'id': 'od9z5r',
     'type': 'line',
     'config': {'dataId': 'FlujoViajes',
      'label': 'Flujo',
      'color': [231, 159, 213],
      'highlightColor': [252, 242, 26, 255],
      'columns': {'lat0': 'PY_Origen',
       'lng0': 'PX_Origen',
       'lat1': 'PY_Destino',
       'lng1': 'PX_Destino',
       'alt0': None,
       'alt1': None},
      'isVisible': True,
      'visConfig': {'opacity': 0.15,
       'thickness': 2,
       'colorRange': {'name': 'Global Warming',
        'type': 'sequential',
        'category': 'Uber',
        'colors': ['#5A1846',
         '#900C3F',
         '#C70039',
         '#E3611C',
         '#F1920E',
         '#FFC300']},
       'sizeRange': [0, 13.4],
       'targetColor': [82, 163, 83],
       'elevationScale': 0},
      'hidden': False,
      'textLabel': [{'field': None,
        'color': [255, 255, 255],
        'size': 18,
        'offset': [0, 0],
        'anchor': 'start',
        'alignment': 'center'}]},
     'visualChannels': {'colorField': None,
      'colorScale': 'quantile',
      'sizeField': {'name': 'Total', 'type': 'integer'},
      'sizeScale': 'sqrt'}}],
   'interactionConfig': {'tooltip': {'fieldsToShow': {'Zonas': [{'name': 'CODIGO_MZ',
        'format': None}],
      'FlujoViajes': [{'name': 'Caminando', 'format': None},
       {'name': 'Transporte Colectivo', 'format': None},
       {'name': 'Taxi', 'format': None},
       {'name': 'Bicicleta', 'format': None},
       {'name': 'Motocicleta', 'format': None}]},
     'compareMode': False,
     'compareType': 'absolute',
     'enabled': True},
    'brush': {'size': 0.5, 'enabled': False},
    'geocoder': {'enabled': False},
    'coordinate': {'enabled': False}},
   'layerBlending': 'normal',
   'splitMaps': [],
   'animationConfig': {'currentTime': None, 'speed': 1}},
  'mapState': {'bearing': 0,
   'dragRotate': False,
   'latitude': 20.569629840077784,
   'longitude': -103.68190457934014,
   'pitch': 0,
   'zoom': 8.349332977080866,
   'isSplit': False},
  'mapStyle': {'styleType': 'dark',
   'topLayerGroups': {},
   'visibleLayerGroups': {'label': True,
    'road': True,
    'border': False,
    'building': True,
    'water': True,
    'land': True,
    '3d building': False},
   'threeDBuildingColor': [9.665468314072013,
    17.18305478057247,
    31.1442867897876],
   'mapStyles': {}}}}
    
    map_clean2 = keplergl.KeplerGl(data={'Zonas': zonas.drop(toDrop, axis = 1), 'FlujoViajes': fluxData}, config = config2)
    map_clean2.save_to_html(file_name=map2Path)

    #! Closing Process
    arcpy.AddMessage('Finishing Process')
    arcpy.management.Delete('in_memory')