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


def script_tool(param0, param1):
    """Script code goes below"""
    # Create Pivot Table of Acts
    tmpTable = arcgis_table_to_df(param0)
    tmpTable2 = tmpTable.pivot_table(values = 'Point_Count', index = 'JOIN_ID', columns = 'codigo_act', aggfunc='sum', fill_value = 0).add_prefix('act_').reset_index()

    return tmpTable2


if __name__ == "__main__":

    param0 = arcpy.GetParameter(0)
    param1 = arcpy.GetParameter(1)

    tmpTable = script_tool(param0, param1)
    tmpArray = tmpTable.to_records(index = False)

    arcpy.da.NumPyArrayToTable(tmpArray, param1)