"""Diagnostic to select grid points within a shapefile."""
from copy import deepcopy
import logging
import os
import sys
from netCDF4 import Dataset
import shapefile
from shapely.geometry import MultiPoint
from shapely.geometry import shape, Point
from shapely.geometry.multipolygon import MultiPolygon
from shapely.ops import nearest_points
import numpy as np

import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap
import iris
from esmvaltool.diag_scripts.shared import run_diagnostic
from esmvaltool.diag_scripts.shared.plot import quickplot

logger = logging.getLogger(os.path.basename(__file__))


def main(cfg):
    """Select grid points within shapefiles."""
    for filename, attributes in cfg['input_data'].items():
        logger.info("Processing variable %s from model %s",
                    attributes['standard_name'], attributes['model'])
        logger.debug("Loading %s", filename)
        cube = iris.load_cube(filename)
        polyid, var = shapeselect(cfg, cube, filename)
        name = os.path.splitext(os.path.basename(filename))[0] + '_polygon'
        if cfg['write_csv']:
            path = os.path.join(
                cfg['work_dir'],
                name + '.csv',
            )
            with open(path, 'w') as file:
                file.write("id time \n")
                file.close()
                tvar = deepcopy(var)
                tvar = np.transpose(tvar)
                np.savetxt(path, tvar, delimiter=',')

        if cfg['write_netcdf']:
            path = os.path.join(
                cfg['work_dir'],
                name + '.nc',
            )
            write_netcdf(path, polyid, var, cube, cfg)


def shapeselect(cfg, cube, filename):
    """
    Add some description here

    Two lines
    """
    shppath = cfg['shppath']
    shpidcol = cfg['shpidcol']
    wgtmet = cfg['wgtmet']
    if ((cube.coord('latitude').ndim == 1 and
         cube.coord('longitude').ndim == 1)):
        coord_points = [(x, y) for x in cube.coord('latitude').points
                        for y in cube.coord('longitude').points]
    # if lat and lon are matrices
    elif (cube.coord('latitude').ndim == 2 and
          cube.coord('longitude').ndim == 2):
        logger.info("Matrix coords not yet implemented with iris!")
        sys.exit(1)
    else:
        logger.info("Unexpected error: " +
                    "Inconsistency between grid lon and lat dimensions")
        sys.exit(1)
    points = MultiPoint(coord_points)
    # Import shapefile with catchments
    shp = shapefile.Reader(shppath)
    shapes = shp.shapes()
    fields = shp.fields[1:]
    records = shp.records()
    attr = [[records[i][j] for i in range(len(records))]
            for j in range(len(fields))]
    for shpid, xfld in enumerate(fields):
        if xfld[0] == shpidcol:
            index_poly_id = shpid
            break
    else:
        logger.info("%s not in shapefile!", shpid)
        sys.exit(1)
    poly_id = attr[index_poly_id]

    # This should be a loop over shapes instead
    # Then we are flexible to chose new method if one fails
    # if wgtmet == x:
    #    try:
    #        call method centroid_inside
    #    exception method fail:
    #        call method2 centroid
    #
    # --  Method: nearest_centroid ---
    if wgtmet == 'nearest_centroid':
        # get polygon centroids
        mulpol = MultiPolygon([shape(pol) for pol in shapes])
        cent = MultiPoint([pol.centroid for pol in mulpol])
        # find nearest point in netcdf grid for each catchment centroid
        selected_points = []
        for i in cent:
            nearest = nearest_points(i, points)
            nearestgplon = np.where(cube.coord('longitude').points ==
                                    nearest[1].coords[0][1])
            nearestgplat = np.where(cube.coord('latitude').points ==
                                    nearest[1].coords[0][0])
            selected_points.append(list((nearestgplon[0], nearestgplat[0])))
            # Add a check if the point is inside polygon
            # when looping over shapes:
            # point = Point(lon, lat)
            # shapeX.contains(point)
            # Issue warning if outside
            # Implement forced inside (see https://stackoverflow.com/questions/33311616/find-coordinate-of-closest-point-on-polygon-shapely/33324058 )
        var = np.zeros((len(cube.coord('time').points), len(poly_id)))
        cnt = 0
        for point in selected_points:
            var[:, cnt] = np.squeeze(cube.data[:, point[0], point[1]])
            cnt += 1
    else:
        logger.info('ERROR: invalid weighting method %s', wgtmet)
        sys.exit(1)
    if cfg['evalplot']:
        shape_plot(selected_points, cube, filename, cfg)
    return poly_id, var


def shape_plot(selected_points, cube, filename, cfg):
    """Plot shapefiles and included grid points"""
    shppath = cfg['shppath']
    lons = []
    lats = []
    for xx, yy in selected_points:
        lons.append(cube.coord('longitude').points[xx][0]) #point[0]])
        lats.append(cube.coord('latitude').points[yy][0]) #point[1]])
    # Set limits for map (This can definitely be improved!)
    shp = shapefile.Reader(shppath)
    llcrnrlon=shp.bbox[0]-15
    llcrnrlat=max((shp.bbox[2]-1,-90))
    urcrnrlon=shp.bbox[1]+15
    urcrnrlat=min((shp.bbox[3]+1,90))
    # Read all model points within map limits
    if ((cube.coord('latitude').ndim == 1 and
         cube.coord('longitude').ndim == 1)):
        coord_points = [(x, y) for x in cube.coord('latitude').points
                        for y in cube.coord('longitude').points]
    elif (cube.coord('latitude').ndim == 2 and
          cube.coord('longitude').ndim == 2):
        logger.info("Matrix coords not yet implemented with iris!")
        sys.exit(1)
    else:
        logger.info("Unexpected error: " +
                    "Inconsistency between grid lon and lat dimensions")
        sys.exit(1)
    alons = []
    alats = []
    for lat, lon in coord_points:
        alons.append(lon)
        alats.append(lat)
    map = Basemap(llcrnrlon=llcrnrlon, llcrnrlat=llcrnrlat,
                  urcrnrlon=urcrnrlon, urcrnrlat=urcrnrlat, 
                  projection='tmerc',
                  lat_0=0, lon_0=0)
    map.drawmapboundary()
    map.drawcoastlines()
    map.readshapefile(shppath[0:-4], 'obj', color='red')
    map.scatter(alats, alons, 3, marker='o', latlon=True, color='gray')
    map.scatter(lats, lons, 6, marker='x', latlon=True, color='red')
    plt.show()
    #name = os.path.splitext(os.path.basename(filename))[0]
    #path = os.path.join(cfg['work_dir'], name + '.png',)
    #plt.savefig(path)

def write_netcdf(path, polyid, var, cube, cfg):
    """Write results to a netcdf file."""
    shppath = cfg['shppath']
    # wgtmet = cfg['wgtmet']
    ncout = Dataset(path, mode='w')
    ncout.createDimension('time', None)
    ncout.createDimension('polygon', len(polyid))
    times = ncout.createVariable('time', 'f8', ('time'), zlib=True)
    times.setncattr_string('standard_name', cube.coord('time').standard_name)
    times.setncattr_string('long_name', cube.coord('time').long_name)
    # if isinstance(cube.coord('time').units, str):
    #     times.setncattr_string('units',cube.coord('time').units)
    # else:
    #     tunit = cube.coord('time').units
    times.setncattr_string('calendar', cube.coord('time').units.calendar)
    times.setncattr_string('units', cube.coord('time').units.origin)
    polys = ncout.createVariable('polygon', 'f4', ('polygon'), zlib=True)
    polys.setncattr_string('standard_name', 'polygon')
    polys.setncattr_string('long_name', 'polygon')
    polys.setncattr_string('shapefile', shppath)
    data = ncout.createVariable(cube.var_name, 'f4', ('time', 'polygon'),
                                zlib=True)
    data.setncattr_string('standard_name', cube.standard_name)
    data.setncattr_string('long_name', cube.long_name)
    data.setncattr_string('units', cube.units.origin)
    for key, val in cube.metadata[-2].items():
        ncout.setncattr_string(key, val)
    times[:] = cube.coord('time').points
    polys[:] = polyid[:]
    data[:] = var[:]
    ncout.close()


if __name__ == '__main__':
    with run_diagnostic() as config:
        main(config)