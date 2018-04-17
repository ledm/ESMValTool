'''
Stratospheric assessment code
'''
import os

import matplotlib as mpl
import matplotlib.cm as mpl_cm
import matplotlib.colors as mcol
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

from cartopy.mpl.gridliner import LATITUDE_FORMATTER
import iris
import iris.analysis.cartography as iac
import iris.coord_categorisation as icc
import iris.plot as iplt

from ..auto_assess_deprecated.loaddata import load_run_ss
from ..utility.plotting import segment2list

MARKERS = 'ops*dh^v<>+xDH.,'

# Candidates for general utility functions

def weight_lat_ave(cube):
    '''
    Routine to calculate weighted latitudinal average
    '''
    grid_areas = iac.area_weights(cube)
    return cube.collapsed('latitude', iris.analysis.MEAN, weights=grid_areas)


def cmap_and_norm(cmap, levels, reverse=False):
    '''
    Routine to generate interpolated colourmap and normalisation from
    given colourmap and level set.
    '''
    # cmap must be a registered colourmap
    tcmap = mpl_cm.get_cmap(cmap)
    colourmap = segment2list(tcmap, levels.size, reverse=reverse)
    normalisation = mcol.BoundaryNorm(levels, levels.size-1)
    return colourmap, normalisation


def add_contour_lines(cube, lev, skipline=1, skiplabel=1,
                      thick=1.5, thin=0.75):
    '''
    Routine to add labelled contour lines to filled contour plot to highlight
    contour boundaries. Adds thicker line at zero contour and can skip contour
    lines if necessary.
    '''
    levels = lev[::skipline]
    # This sets up contour line widths to be thick for zero and thin otherwise
    lwid = thick * np.ones_like(levels)
    lwid[levels.nonzero()] = thin
    # Plot line contours - black lines gives solid for +ve and dashed for -ve
    cl1 = iplt.contour(cube, colors='k', linewidths=lwid, levels=levels)
    # Set to label every line with appropriate string size and formatting
    plt.clabel(cl1, levels[::skiplabel], inline=1, fontsize=6, fmt='%1.0f')


def plot_zmean(cube, levels, title, log=False, ax1=None):
    '''
    Routine to plot zonal mean fields as latitude-pressure contours with given
    contour levels
    Option to plot against log(pressure)
    '''
    (colormap, normalisation) = cmap_and_norm('brewer_RdBu_11', levels)
    if ax1 is None:
        ax1 = plt.gca()
    ax1.set_title(title)
    cf1 = iplt.contourf(cube, levels=levels, cmap=colormap, norm=normalisation)
    add_contour_lines(cube, cf1.levels, skiplabel=2)
    ax1.set_xlabel('Latitude', fontsize='small')
    ax1.set_xlim(-90, 90)
    ax1.set_xticks([-90, -60, -30, 0, 30, 60, 90])
    ax1.xaxis.set_major_formatter(LATITUDE_FORMATTER)
    ax1.set_ylabel('Pressure (hPa)', fontsize='small')
    ax1.set_ylim(1000, 0.1)
    if log:
        ax1.set_yscale("log")


def plot_timehgt(cube, levels, title, log=False, ax1=None):
    '''
    Routine to plot fields as time-pressure contours with given
    contour levels
    Option to plot against log(pressure)
    '''
    (colormap, normalisation) = cmap_and_norm('brewer_RdBu_11', levels)
    if ax1 is None:
        ax1 = plt.gca()
    ax1.set_title(title)
    cf1 = iplt.contourf(cube, levels=levels, cmap=colormap, norm=normalisation)
    add_contour_lines(cube, cf1.levels, skipline=2)
    # Convert the time unit to time_coord.points[0], i.e 2012-09-14 04:05:00
    ax1.set_xlabel('Year', fontsize='small')
    time_coord = cube.coord('time')
    new_epoch = time_coord.points[0]
    new_unit_str = 'hours since {}'
    new_unit = new_unit_str.format(time_coord.units.num2date(new_epoch))
    # VPREDOI
    # there is something dodgy going on here
    # it's complaining year is out of range
    ax1.xaxis.axis_date()
    ax1.xaxis.set_label(new_unit)
    ax1.xaxis.set_major_locator(mdates.YearLocator(4))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax1.set_ylabel('Pressure (hPa)', fontsize='small')
    ax1.set_ylim(1000, 0.1)
    if log:
        ax1.set_yscale("log")


# Routines specific to stratosphere assessment

def plot_uwind(cube, month, filename):
    '''
    Routine to plot zonal mean zonal wind on log pressure scale
    '''
    levels = np.arange(-120, 121, 10)
    title = 'Zonal mean zonal wind ({})'.format(month)
    fig = plt.figure()
    plot_zmean(cube, levels, title, log=True)
    fig.savefig(filename)
    plt.close()


def plot_temp(cube, season, filename):
    '''
    Routine to plot zonal mean temperature on log pressure scale
    '''
    levels = np.arange(160, 321, 10)
    title = 'Temperature ({})'.format(season)
    fig = plt.figure()
    plot_zmean(cube, levels, title, log=True)
    fig.savefig(filename)
    plt.close()


def plot_qbo(cube, filename):
    '''
    Routine to create time-height plot of 5S-5N mean zonal mean U
    '''
    levels = np.arange(-80, 81, 10)
    title = 'QBO'
    fig = plt.figure(figsize=(12, 6))
    plot_timehgt(cube, levels, title, log=True)
    fig.savefig(filename)
    plt.close()


def calc_qbo_index(qbo):
    '''
    Routine to calculate QBO indices

    The segment of code you include scans the timeseries of U (30hPa) and looks
    for the times where this crosses the zero line.  Essentially U(30hPa)
    oscillates between positive and negative, and we're looking for a period,
    defined as the length of time between where U becomes positive and then goes
    negative and then becomes positive again (or negative/positive/negative).
    Also, periods less than 12 months are discounted.
    '''
    ufin = qbo.data

    indiciesdown, indiciesup = find_zero_crossings(ufin)
    counterup = len(indiciesup)
    counterdown = len(indiciesdown)

    # Did we start on an upwards or downwards cycle?
    if (indiciesdown[0] < indiciesup[0]):
        (kup, kdown) = (0, 1)
    else:
        (kup, kdown) = (1, 0)
    # Translate upwards and downwards indices into U wind values
    periodsmin = counterup - kup
    periodsmax = counterdown - kdown
    valsup = np.zeros(periodsmax)
    valsdown = np.zeros(periodsmin)
    for i in range(periodsmin):
        valsdown[i] = np.amin(ufin[indiciesdown[i]:indiciesup[i+kup]])
    for i in range(periodsmax):
        valsup[i] = np.amax(ufin[indiciesup[i]:indiciesdown[i+kdown]])
    # Calculate eastward QBO amplitude
    counter = 0
    totvals = 0
    for i in range(periodsmax):
        if (valsup[i] > 10.):
            totvals = totvals+valsup[i]
            counter = counter+1
    if (counter == 0):
        ampl_east = 0.
    else:
        totvals = totvals/counter
        ampl_east = totvals
    # Calculate westward QBO amplitude
    counter = 0
    totvals = 0
    for i in range(periodsmin):
        if (valsdown[i] < -20.):
            totvals = totvals+valsdown[i]
            counter = counter+1
    if (counter == 0):
        ampl_west = 0.
    else:
        totvals = totvals/counter
        ampl_west = -totvals
    # Calculate QBO period, set to zero if no full oscillations in data
    period1 = 0.0
    period2 = 0.0
    if counterdown > 1:
        period1 = (indiciesdown[counterdown-1]-indiciesdown[0])/(counterdown-1)
    if counterup > 1:
        period2 = (indiciesup[counterup-1]-indiciesup[0])/(counterup-1)
    # Pick larger oscillation period
    if period1 < period2:
        period = period2
    else:
        period = period1
    return (period, ampl_west, ampl_east)


def flatten_list(list_):
    """
    Turn list of lists into a list of all elements.
    [[1], [2, 3]] -> [1, 2, 3]
    """
    return [item for sublist in list_ for item in sublist]


def find_zero_crossings(array):
    """
    Finds zero crossings in 1D iterable.

    Returns two lists with indices, last_pos and last_neg.
    If a zero crossing includes zero, zero is used as last positive
    or last negative value.

    :param array: 1D iterable.
    :returns (last_pos, last_neg): Tuples with indices before sign change.
        last_pos: indices of positive values with consecutive negative value.
        last_neg: indices of negative values with consecutive positive value.
    """
    signed_array = np.sign(array)  # 1 if positive and -1 if negative
    diff = np.diff(signed_array)  # difference of one item and the next item

    # sum differences in case zero is included in zero crossing
    # array:  [-1, 0, 1]
    # signed: [-1, 0, 1]
    # diff:   [ 1, 1]
    # sum:    [ 0, 2]
    for i, d in enumerate(diff):
        if i < len(diff) - 1:  # not last item
            if d != 0 and d == diff[i+1]:
                diff[i+1] = d + diff[i+1]
                diff[i] = 0

    last_neg = np.argwhere(diff == 2)
    last_pos = np.argwhere(diff == -2)
    last_neg = flatten_list(last_neg)
    last_pos = flatten_list(last_pos)
    return last_pos, last_neg


def pnj_strength(cube, winter=True):
    '''
    Calculate PNJ and ENJ strength as max/(-min) of zonal mean U wind
    for nh/sh in winter and sh/nh in summer repsectively.
    '''
    # Extract regions of interest
    notrop = iris.Constraint(air_pressure=lambda p: p < 80.0)
    nh_cons = iris.Constraint(latitude=lambda l: l > 0)
    sh_cons = iris.Constraint(latitude=lambda l: l < 0)
    nh_tmp = cube.extract(notrop & nh_cons)
    sh_tmp = cube.extract(notrop & sh_cons)

    # Calculate max/min depending on season
    coords = ['latitude', 'air_pressure']
    if winter:
        pnj_max = nh_tmp.collapsed(coords, iris.analysis.MAX)
        pnj_min = sh_tmp.collapsed(coords, iris.analysis.MIN) * (-1.0)
    else:
        pnj_max = sh_tmp.collapsed(coords, iris.analysis.MAX)
        pnj_min = nh_tmp.collapsed(coords, iris.analysis.MIN) * (-1.0)
    return (pnj_max, pnj_min)


def pnj_metrics(run, ucube, metrics):
    '''
    Routine to calculate PNJ strength metrics from zonal mean U
    Also produce diagnostic plots of zonal mean U
    '''
    # TODO side effect: changes metrics without returning

    # Extract U for January and average over years
    jancube = ucube.extract(iris.Constraint(month_number=1))
    jan_annm = jancube.collapsed('time', iris.analysis.MEAN)

    # Extract U for July and average over years
    julcube = ucube.extract(iris.Constraint(month_number=7))
    jul_annm = julcube.collapsed('time', iris.analysis.MEAN)

    # Calculate PNJ and ENJ strengths
    (jan_pnj, jan_enj) = pnj_strength(jan_annm, winter=True)
    (jul_pnj, jul_enj) = pnj_strength(jul_annm, winter=False)

    # Add to metrics dictionary
    metrics['Polar night jet: northern hem (January)'] = jan_pnj.data
    metrics['Polar night jet: southern hem (July)'] = jul_pnj.data
    metrics['Easterly jet: southern hem (January)'] = jan_enj.data
    metrics['Easterly jet: northern hem (July)'] = jul_enj.data

    # Plot U(Jan) and U(Jul)
    plot_uwind(jan_annm, 'January', '{}_u_jan.png'.format(run['runid']))
    plot_uwind(jul_annm, 'July', '{}_u_jul.png'.format(run['runid']))


def qbo_metrics(run, ucube, metrics):
    '''
    Routine to calculate QBO metrics from zonal mean U
    '''
    # TODO side effect: changes metrics without returning
    # Extract equatorial zonal mean U
    tropics = iris.Constraint(latitude=lambda l: -5 <= l <= 5)
    p30 = iris.Constraint(air_pressure=30.)
    qbo = weight_lat_ave(ucube.extract(tropics))
    qbo30 = qbo.extract(p30)

    # write results to current working directory
    outfile = '{0}_qbo30_{1}.nc'
    with iris.FUTURE.context(netcdf_no_unlimited=True):
        iris.save(qbo30, outfile.format(run['runid'], run.period))

    # Calculate QBO metrics
    (period, amp_west, amp_east) = calc_qbo_index(qbo30)

    # Add to metrics dictionary
    metrics['QBO period at 30 hPa'] = period
    metrics['QBO amplitude at 30 hPa (westward)'] = amp_west
    metrics['QBO amplitude at 30 hPa (eastward)'] = amp_east

    # Plot QBO and timeseries of QBO at 30hPa
    plot_qbo(qbo, '{}_qbo.png'.format(run['runid']))


def tpole_metrics(run, tcube, metrics):
    '''
    Routine to calculate polar 50hPa temperature metrics from zonal mean
    temperature
    Also produce diagnostic plots of zonal mean temperature
    '''
    # TODO side effect: changes metrics without returning
    # Calculate and extract seasonal mean temperature
    t_seas_mean = tcube.aggregated_by('clim_season', iris.analysis.MEAN)
    t_djf = t_seas_mean.extract(iris.Constraint(clim_season='djf'))
    t_mam = t_seas_mean.extract(iris.Constraint(clim_season='mam'))
    t_jja = t_seas_mean.extract(iris.Constraint(clim_season='jja'))
    t_son = t_seas_mean.extract(iris.Constraint(clim_season='son'))

    # Calculate area averages over polar regions at 50hPa
    nhpole = iris.Constraint(latitude=lambda l: l >= 60, air_pressure=50.0)
    shpole = iris.Constraint(latitude=lambda l: l <= -60, air_pressure=50.0)

    djf_polave = weight_lat_ave(t_djf.extract(nhpole))
    mam_polave = weight_lat_ave(t_mam.extract(nhpole))
    jja_polave = weight_lat_ave(t_jja.extract(shpole))
    son_polave = weight_lat_ave(t_son.extract(shpole))

    # Calculate metrics and add to metrics dictionary
    # TODO Why take off 180.0?
    metrics['50 hPa temperature: 60N-90N (DJF)'] = djf_polave.data - 180.
    metrics['50 hPa temperature: 60N-90N (MAM)'] = mam_polave.data - 180.
    metrics['50 hPa temperature: 90S-60S (JJA)'] = jja_polave.data - 180.
    metrics['50 hPa temperature: 90S-60S (SON)'] = son_polave.data - 180.

    # Plot T(DJF) and T(JJA)
    plot_temp(t_djf, 'DJF', '{}_t_djf.png'.format(run['runid']))
    plot_temp(t_jja, 'JJA', '{}_t_jja.png'.format(run['runid']))


def mean_and_strength(cube):
    '''
    Calculate mean and strength of equatorial temperature seasonal
    cycle
    '''
    # Calculate mean, max and min values of seasonal timeseries
    tmean = cube.collapsed('time', iris.analysis.MEAN)
    tmax = cube.collapsed('time', iris.analysis.MAX)
    tmin = cube.collapsed('time', iris.analysis.MIN)
    tstrength = (tmax-tmin) / 2.
    # TODO Why take off 180.0?
    return (tmean.data - 180.0, tstrength.data)


def t_mean(cube):
    '''
    Calculate mean equatorial 100hPa temperature
    '''
    tmean = cube.collapsed('time', iris.analysis.MEAN)
    return tmean.data


def q_mean(cube):
    '''
    Calculate mean tropical 70hPa water vapour
    '''
    qmean = cube.collapsed('time', iris.analysis.MEAN)
    # TODO magic numbers
    return ((1000000.*29./18.)*qmean.data)   # ppmv


def teq_metrics(run, tcube, metrics):
    '''
    Routine to calculate equatorial 100hPa temperature metrics
    '''
    # Extract equatorial temperature at 100hPa
    equator = iris.Constraint(latitude=lambda l: -2 <= l <= 2)
    p100 = iris.Constraint(air_pressure=100.)
    teq100 = tcube.extract(equator & p100)

    # Calculate area-weighted global monthly means from multi-annual data
    t_months = teq100.aggregated_by('month', iris.analysis.MEAN)
    t_months = weight_lat_ave(t_months)

    # write results to current working directory
    outfile = '{0}_teq100_{1}.nc'
    with iris.FUTURE.context(netcdf_no_unlimited=True):
        iris.save(t_months, outfile.format(run['runid'], run.period))

    # Calculate metrics
    (tmean, tstrength) = mean_and_strength(t_months)

    # Add to metrics dictionary
    metrics['100 hPa equatorial temp (annual mean)'] = tmean
    metrics['100 hPa equatorial temp (annual cycle strength)'] = tstrength


def t_metrics(run, tcube, metrics):
    '''
    Routine to calculate 10S-10N 100hPa temperature metrics
    '''
    # TODO side effect: changes metrics without returning
    # Extract 10S-10N temperature at 100hPa
    equator = iris.Constraint(latitude=lambda l: -10 <= l <= 10)
    p100 = iris.Constraint(air_pressure=100.)
    t100 = tcube.extract(equator & p100)

    # Calculate area-weighted global monthly means from multi-annual data
    t_months = t100.aggregated_by('month', iris.analysis.MEAN)
    t_months = weight_lat_ave(t_months)

    # write results to current working directory
    outfile = '{0}_t100_{1}.nc'
    with iris.FUTURE.context(netcdf_no_unlimited=True):
        iris.save(t_months, outfile.format(run['runid'], run.period))

    # Calculate metrics
    (tmean, tstrength) = mean_and_strength(t_months)

    # Add to metrics dictionary
    metrics['100 hPa 10Sto10N temp (annual mean)'] = tmean
    metrics['100 hPa 10Sto10N temp (annual cycle strength)'] = tstrength


def q_metrics(run, qcube, metrics):
    '''
    Routine to calculate 10S-10N 70hPa water vapour metrics
    '''
    # TODO side effect: changes metrics without returning
    # Extract 10S-10N humidity at 100hPa
    tropics = iris.Constraint(latitude=lambda l: -10 <= l <= 10)
    p70 = iris.Constraint(air_pressure=70.)
    q70 = qcube.extract(tropics & p70)

    # Calculate area-weighted global monthly means from multi-annual data
    q_months = q70.aggregated_by('month', iris.analysis.MEAN)
    q_months = weight_lat_ave(q_months)

    # write results to current working directory
    outfile = '{0}_q70_{1}.nc'
    with iris.FUTURE.context(netcdf_no_unlimited=True):
        iris.save(q_months, outfile.format(run['runid'], run.period))

    # Calculate metrics
    qmean = q_mean(q_months)

    # Add to metrics dictionary
    metrics['70 hPa 10Sto10N wv (annual mean)'] = qmean


def summary_metric(metrics):
    '''
    This is a weighted average of all 13 metrics,
    giving equal weights to the averages of extratropical U,
    extratropical T, QBO, and equatorial T metrics.
    '''
    # TODO side effect: changes metrics without returning
    pnj_metric = metrics['Polar night jet: northern hem (January)'] \
        + metrics['Polar night jet: southern hem (July)'] \
        + metrics['Easterly jet: southern hem (January)'] \
        + metrics['Easterly jet: northern hem (July)']
    t50_metric = metrics['50 hPa temperature: 60N-90N (DJF)'] \
        + metrics['50 hPa temperature: 60N-90N (MAM)'] \
        + metrics['50 hPa temperature: 90S-60S (JJA)'] \
        + metrics['50 hPa temperature: 90S-60S (SON)']
    qbo_metric = metrics['QBO period at 30 hPa'] \
        + metrics['QBO amplitude at 30 hPa (westward)'] \
        + metrics['QBO amplitude at 30 hPa (eastward)']
    teq_metric = metrics['100 hPa equatorial temp (annual mean)'] \
        + metrics['100 hPa equatorial temp (annual cycle strength)']
    q_metric = metrics['70 hPa 10Sto10N wv (annual mean)']
    # TODO magic numbers
    summary = ((pnj_metric / 4.) + (2.4 * t50_metric / 4.) + (3.1 * qbo_metric / 3.)
               + (8.6 * teq_metric / 2.) + (18.3 * q_metric)) / 33.4

    # Add to metrics dictionary
    metrics['Summary'] = summary


def mainfunc(run):
    '''
    Main function in stratospheric assessment code
    '''
    metrics = dict()

    # Set up to only run for 10 year period (eventually)
    year_cons = dict(from_dt=run['from_monthly'], to_dt=run['to_monthly'])

    # Read zonal mean U (lbproc=192) and add month number to metadata
    # ucube = load_run_ss(run, 'monthly', 'x_wind', lbproc=192, **year_cons)  # m01s30i201
    ucube = load_run_ss(run, 'monthly', 'eastward_wind', lbproc=192, **year_cons)
    # Although input data is a zonal mean, iris does not recognise it as such
    # and just reads it as having a single longitudinal coordinate. This
    # removes longitude as a dimension coordinate and makes it a scalar
    # coordinate in line with how a zonal mean would be described.
    # Is there a better way of doing this?
    ucube = ucube.collapsed('longitude', iris.analysis.MEAN)
    # ESMValTool files already have bounds and months
    # ucube.coord('latitude').guess_bounds()
    # icc.add_month_number(ucube, 'time', name='month_number')

    # Read zonal mean T (lbproc=192) and add clim month and season to metadata
    tcube = load_run_ss(run, 'monthly', 'air_temperature', lbproc=192,
                        **year_cons)  # m01s30i204
    # Although input data is a zonal mean, iris does not recognise it as such
    # and just reads it as having a single longitudinal coordinate. This
    # removes longitude as a dimension coordinate and makes it a scalar
    # coordinate in line with how a zonal mean would be described.
    # Is there a better way of doing this?
    tcube = tcube.collapsed('longitude', iris.analysis.MEAN)
    # ESMValTool files already have bounds and months
    # tcube.coord('latitude').guess_bounds()
    icc.add_month(tcube, 'time', name='month')
    icc.add_season(tcube, 'time', name='clim_season')

    # Read zonal mean q (lbproc=192) and add clim month and season to metadata
    qcube = load_run_ss(run, 'monthly', 'specific_humidity', lbproc=192,
                        **year_cons)  # m01s30i205
    # Although input data is a zonal mean, iris does not recognise it as such
    # and just reads it as having a single longitudinal coordinate. This
    # removes longitude as a dimension coordinate and makes it a scalar
    # coordinate in line with how a zonal mean would be described.
    # Is there a better way of doing this?
    qcube = qcube.collapsed('longitude', iris.analysis.MEAN)
    # ESMValTool files already have bounds and months
    # qcube.coord('latitude').guess_bounds()
    icc.add_month(qcube, 'time', name='month')
    icc.add_season(qcube, 'time', name='clim_season')

    # Calculate PNJ metrics
    pnj_metrics(run, ucube, metrics)

    # Calculate QBO metrics
    qbo_metrics(run, ucube, metrics)

    # Calculate polar temperature metrics
    tpole_metrics(run, tcube, metrics)

    # Calculate equatorial temperature metrics
    teq_metrics(run, tcube, metrics)

    # Calculate tropical temperature metrics
    t_metrics(run, tcube, metrics)

    # Calculate tropical water vapour metric
    q_metrics(run, qcube, metrics)

    # Summary metric
    summary_metric(metrics)

    # Make sure all metrics are of type float
    # Need at the moment to populate metrics files
    for key, value in metrics.items():
        metrics[key] = float(value)

    return metrics


def multi_qbo_plot(runs):
    '''
    Plot 30hPa QBO (5S to 5N) timeseries comparing experiments on one plot
    '''
    # TODO avoid running mainfunc

    # Run mainfunc for each run.
    # mainfunc returns metrics and writes results into an *.nc in the current
    # working directory.
    # To make this function indendent of previous call to mainfunc, mainfunc
    # is run again for each run in this function
    #
    # This behaviour is due to the convention that only metric_functions can
    # return metric values, multi_functions are supposed to
    # only produce plots (see __init__.py).

    # rerun mainfunc for each run
    for run in runs:
        _ = mainfunc(run)

    # Split up control and experiments
    run_cntl = runs[0]
    run_expts = runs[1:]

    # QBO at 30hPa timeseries plot

    # Set up generic input file name
    infile = '{0}_qbo30_{1}.nc'

    # Create control filename
    cntlfile = infile.format(run_cntl['runid'], run_cntl.period)

    # Create experiment filenames
    exptfiles = dict()
    for run_expt in run_expts:
        exptfiles[run_expt.id] = infile.format(run['runid'], run_expt.period)

    # If no control data then stop ...
    if not os.path.exists(cntlfile):
        print '30hPa QBO for control absent. skipping ...'
        return

    # Create plot
    fig = plt.figure()
    ax1 = plt.gca()
    # Plot control
    qbo30_cntl = iris.load_cube(cntlfile)
    iplt.plot(qbo30_cntl, label=run_cntl.id)
    # Plot experiments
    for run_expt in run_expts:
        exptfile = exptfiles[run_expt.id]
        if os.path.exists(exptfile):
            qbo30_expt = iris.load_cube(exptfile)
            iplt.plot(qbo30_expt, label=run_expt.id)
    ax1.set_title('QBO at 30hPa')
    ax1.set_xlabel('Time', fontsize='small')
    ax1.set_ylabel('U (m/s)', fontsize='small')
    ax1.legend(loc='upper left', fontsize='small')
    fig.savefig('qbo_30hpa.png')
    plt.close()


def multi_teq_plot(runs):
    '''
    Plot 100hPa equatorial temperature seasonal cycle comparing
    experiments on one plot
    '''
    # TODO avoid running mainfunc

    # Run mainfunc for each run.
    # mainfunc returns metrics and writes results into an *.nc in the current
    # working directory.
    # To make this function indendent of previous call to mainfunc, mainfunc
    # is run again for each run in this function
    #
    # This behaviour is due to the convention that only metric_functions can
    # return metric values, multi_functions are supposed to
    # only produce plots (see __init__.py).

    # rerun mainfunc for each run
    for run in runs:
        _ = mainfunc(run)

    # Split up control and experiments
    run_cntl = runs[0]
    run_expts = runs[1:]

    # Set up generic input file name
    infile = '{0}_teq100_{1}.nc'

    # Create control filename
    cntlfile = infile.format(run_cntl['runid'], run_cntl.period)

    # Create experiment filenames
    exptfiles = dict()
    for run_expt in run_expts:
        exptfiles[run_expt.id] = infile.format(run_expt['runid'], run_expt.period)

    # If no control data then stop ...
    if not os.path.exists(cntlfile):
        print '100hPa Teq for control absent. skipping ...'
        return

    # Set up generic plot label
    plotlabel = '{0}, mean={1:5.2f}, cycle={2:5.2f}'

    # Create plot
    times = np.arange(12)
    fig = plt.figure()
    ax1 = plt.gca()
    # Plot control
    tmon = iris.load_cube(cntlfile)
    (tmean, tstrg) = mean_and_strength(tmon)
    label = plotlabel.format(run_cntl.id, float(tmean), float(tstrg))
    plt.plot(times, tmon.data, linewidth=2, label=label)
    # Plot experiments
    for run_expt in run_expts:
        exptfile = exptfiles[run_expt.id]
        if os.path.exists(exptfile):
            tmon = iris.load_cube(exptfile)
            (tmean, tstrg) = mean_and_strength(tmon)
            label = plotlabel.format(run_expt.id, float(tmean), float(tstrg))
            plt.plot(times, tmon.data, linewidth=2, label=label)
    ax1.set_title('Equatorial 100hPa temperature, Multi-annual monthly means')
    ax1.set_xlabel('Month', fontsize='small')
    ax1.set_xlim(0, 11)
    ax1.set_xticks(times)
    ax1.set_xticklabels(tmon.coord('month').points, fontsize='small')
    ax1.set_ylabel('T (K)', fontsize='small')
    ax1.legend(loc='upper left', fontsize='small')
    fig.savefig('teq_100hpa.png')
    plt.close()


def calc_merra(run):
    # Load data
    # VPREDOI this is a hack: I replaced MERRA with ERA-Interim data
    # which has only Air_Temperature; need to find MERRA file
    merrafile = os.path.join(run['clim_root'], 'MERRA', 'merra_tropical_area_avg.nc')
    (t,q)=iris.load_cubes(merrafile, ['air_temperature', 'air_temperature'])
    # Strip out required times
    time = iris.Constraint(time=lambda cell: run['from_monthly']
                                             <= cell.point <=
                                             run['to_monthly'])
    with iris.FUTURE.context(cell_datetime_objects=True):
        t = t.extract(time)
        q = q.extract(time)
    # Calculate time mean
    t = t.collapsed('time', iris.analysis.MEAN)
    q = q.collapsed('time', iris.analysis.MEAN)
    # Create return values
    tmerra = t.data                        # K
    # TODO magic numbers
    qmerra = ((1000000.*29./18.)*q.data)   # ppmv
    return tmerra, qmerra


def calc_erai(run):
    # Load data
    eraidir = os.path.join(run['clim_root'], 'ERA-Interim')
    t = iris.load_cube(os.path.join(eraidir, 'erai_t100_tropical_area_avg.nc'))
    q = iris.load_cube(os.path.join(eraidir, 'erai_q70_tropical_area_avg.nc'))
    # Strip out required times
    time = iris.Constraint(time=lambda cell: run['from_monthly']
                                             <= cell.point <=
                                             run['to_monthly'])
    with iris.FUTURE.context(cell_datetime_objects=True):
        t = t.extract(time)
        q = q.extract(time)
    # Calculate time mean
    t = t.collapsed('time', iris.analysis.MEAN)
    q = q.collapsed('time', iris.analysis.MEAN)
    # Create return values
    terai = t.data                        # K
    # TODO magic numbers
    qerai = ((1000000.*29./18.)*q.data)   # ppmv
    return terai, qerai


def multi_t100_vs_q70_plot(runs):
    '''
    Plot mean 100hPa temperature against mean 70hPa humidity
    '''
    # TODO avoid running mainfunc

    # Run mainfunc for each run.
    # mainfunc returns metrics and writes results into an *.nc in the current
    # working directory.
    # To make this function indendent of previous call to mainfunc, mainfunc
    # is run again for each run in this function
    #
    # This behaviour is due to the convention that only metric_functions can
    # return metric values, multi_functions are supposed to
    # only produce plots (see __init__.py).

    # rerun mainfunc for each run
    for run in runs:
        _ = mainfunc(run)

    # Split up control and experiments
    run_cntl = runs[0]
    run_expts = runs[1:]

    # Set up generic input file name
    t_file = '{0}_t100_{1}.nc'
    q_file = '{0}_q70_{1}.nc'

    # Create control filenames
    t_cntl = t_file.format(run_cntl['runid'], run_cntl.period)
    q_cntl = q_file.format(run_cntl['runid'], run_cntl.period)

    # Create experiment filenames
    t_expts = dict()
    q_expts = dict()
    for run_expt in run_expts:
        t_expts[run_expt.id] = t_file.format(run_expt['runid'], run_expt.period)
        q_expts[run_expt.id] = q_file.format(run_expt['runid'], run_expt.period)

    # If no control data then stop ...
    if not os.path.exists(t_cntl):
        print '100hPa T for control absent. skipping ...'
        return

    # If no control data then stop ...
    if not os.path.exists(q_cntl):
        print '70hPa q for control absent. skipping ...'
        return

    # Load MERRA data (currently set to pre-calculated values)
    (t_merra, q_merra) = calc_merra(run_cntl)

    # Load ERA-I data (currently set to pre-calculated values)
    (t_erai, q_erai) = calc_erai(run_cntl)

    ### Create plot
    # Axes
    #   bottom X: temperature bias wrt MERRA
    #   left Y  : water vapour bias wrt MERRA
    #   top X   : temperature bias wrt ERA-I
    #   right Y : water vapour bias wrt ERA-I

    merra_xmin = -1.0
    merra_xmax = 4.0
    merra_ymin = -1.0
    merra_ymax = 3.0
    erai_xmin = merra_xmin + (t_merra - t_erai)
    erai_xmax = merra_xmax + (t_merra - t_erai)
    erai_ymin = merra_ymin + (q_merra - q_erai)
    erai_ymax = merra_ymax + (q_merra - q_erai)

    fig = plt.figure()

    # MERRA axes
    ax1 = plt.gca()
    ax1.set_xlim(merra_xmin, merra_xmax)
    ax1.set_ylim(merra_ymin, merra_ymax)
    ax1.xaxis.set_tick_params(labelsize='small')
    ax1.yaxis.set_tick_params(labelsize='small')
    ax1.set_xlabel('T(10S-10N, 100hPa) bias wrt MERRA (K)', fontsize='large')
    ax1.set_ylabel('q(10S-10N, 70hPa) bias wrt MERRA (ppmv)', fontsize='large')

    # ERA-I axes
    ax2 = ax1.twiny()  # twiny gives second horizontal axis
    ay2 = ax1.twinx()  # twinx gives second vertical axis
    #ax2.set_xlim(erai_xmin, erai_xmax)
    #ay2.set_ylim(erai_ymin, erai_ymax)
    ax2.xaxis.set_tick_params(labelsize='small')
    ay2.yaxis.set_tick_params(labelsize='small')
    ax2.set_xlabel('T(10S-10N, 100hPa) bias wrt ERA-I (K)', fontsize='large')
    ay2.set_ylabel('q(10S-10N, 70hPa) bias wrt ERA-I (ppmv)', fontsize='large')

    # Plot ideal area
    patch = Rectangle((0.0, 0.0), 2.0, 0.2*q_merra[0, 0, 0], fc='lime', ec='None', zorder=0)
    ax1.add_patch(patch)

    # Plot control
    tmon = iris.load_cube(t_cntl)
    tmean = t_mean(tmon) - t_merra
    qmon = iris.load_cube(q_cntl)
    qmean = q_mean(qmon) - q_merra
    label = '{1} ({0})'.format(run_cntl.id, run_cntl.title)
    ax1.scatter(tmean, qmean, s=100, label=label, marker='^')
    # Plot experiments
    for i, run_expt in enumerate(run_expts):
        t_expt = t_expts[run_expt.id]
        q_expt = q_expts[run_expt.id]
        if os.path.exists(t_expt) and os.path.exists(q_expt):
            tmon = iris.load_cube(t_expt)
            tmean = t_mean(tmon) - t_merra
            qmon = iris.load_cube(q_expt)
            qmean = q_mean(qmon) - q_merra
            label = '{1} ({0})'.format(run_expt.id, run_expt.title)
            ax1.scatter(tmean, qmean, s=100, label=label, marker=MARKERS[i])

    ax1.legend(loc='upper right', scatterpoints=1, fontsize='medium')
    fig.savefig('t100_vs_q70.png')
    plt.close()
