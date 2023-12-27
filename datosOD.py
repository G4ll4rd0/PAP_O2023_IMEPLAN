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

def script_tool(od):
    """Script code goes below"""
    od = arcgis_table_to_df(od)
    od.drop([od.index[-1]], inplace = True)
    byOrigen = od.groupby('Origen').sum().drop(['Destino'], axis = 1)
    byDestino = od.groupby('Destino').sum().drop(['Origen'], axis = 1)
    toFrom = byDestino.join(byOrigen, how = 'outer', rsuffix='_origen', lsuffix='_destino')
    toFrom.index.names = ['Ubicación']
    toFrom.reset_index(inplace = True)
    return toFrom


if __name__ == "__main__":

    param0 = arcpy.GetParameter(0)
    param1 = arcpy.GetParameterAsText(1)

    tmpTable = script_tool(param0)
    tmpArray = tmpTable.to_records(index = False)
    
    arcpy.da.NumPyArrayToTable(tmpArray, param1)