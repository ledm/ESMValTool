#! /usr/bin/env python2.7

'''
Program to make a quick plot to test the colour table. This uses a pkl
generated by the main routine in make_plots.py
'''

import optparse
import os
import os.path
import pdb
import sys

import matplotlib.pyplot as plt

# parse command line options
parser = optparse.OptionParser(usage="usage: %prog [options]")
parser.description = "Test plotting program. Uses output from valnote.py when --num_to_save option is used."
parser.add_option("--pub", dest="pub", action="store_true",
                  default=False, help="Validation note is for a publication. Do not output the UMUI job ids, Rose suite ids, observation dates or field names in the final plots. Plot titles only state model name as specified in the source_file.dat and the observation name. Title font size is increased to 20. Also appends _pub to the final validation note folder (so as to not overwrite the original). Please use alongside a short valorder file (pointed to using --valorder) to limit the validation note to just the plots you want in the publication.")
parser.add_option("--format", dest="format", default="screen",
                  help="Output file format. One of: screen, png, eps, pdf. Default = screen. Output file will appear in current working directory and start with test_colours_out")
parser.add_option("--source", dest="source_file", default='source_file.dat',
                  help="Name of source file (defaults to ./source_file.dat)")
parser.add_option("--levels", dest="levels_file", default=None,
                  help="Name of contour levels file (defaults to main levels_file.dat)")
parser.add_option("--plots", dest="plots_file", default=None,
                  help="Name of plots file (defaults to main plots_file.dat)")
parser.add_option("--obs", dest="obs_file", default=None,
                  help="Name of obs file (defaults to main obs_file.dat)")
parser.add_option("--item", dest="item_file", default=None,
                  help="Name of item file (defaults to main item_file.dat)")
parser.add_option("--title", dest="title_file", default=None,
                  help="Name of title file (defaults to main title_file.dat)")

(options, args) = parser.parse_args()

# Deduce input directories
top_level_dir = os.path.dirname(os.path.realpath(__file__))
control_dir = os.path.join(top_level_dir, '../control')
control_dir = os.path.abspath(control_dir)
extras_dir = '/project/cma/ancil/masks'

# Import extra routines that we couldn't import at the start
import globalvar
import rms
import valmod as vm
import make_plots

# Define global variables
globalvar.debug = True
globalvar.pub = options.pub

# Read the control files
print 'Reading control files'
if options.plots_file:
    globalvar.plots_dict = vm.read_control_file(options.plots_file)
else:
    globalvar.plots_dict = vm.read_control_file('plots_file.dat',
                                                ctldir=control_dir)
if options.levels_file:
    globalvar.levels_dict = vm.read_control_file(options.levels_file)
else:
    globalvar.levels_dict = vm.read_control_file('levels_file.dat',
                                                 ctldir=control_dir)
extras_dict = vm.read_info_file(os.path.join(control_dir, 'extras_file.dat'))
if options.title_file:
    title_dict = vm.read_control_file(options.title_file)
else:
    title_dict = vm.read_control_file('title_file.dat', ctldir=control_dir)
if options.item_file:
    globalvar.item_dict = vm.read_control_file(options.obs_file)
else:
    globalvar.item_dict = vm.read_control_file('item_file.dat', ctldir=control_dir)
if options.obs_file:
    obs_dict = vm.read_control_file(options.obs_file)
else:
    obs_dict = vm.read_control_file('obs_file.dat', ctldir=control_dir)

# Set the source file
if options.source_file:
    if options.source_file == 'code':
        # Special case of setting source_file to 'code' makes this use
        # the sourse_file.dat in the local control directory
        globalvar.source_file = os.path.join(control_dir, 'source_file.dat')
    else:
        globalvar.source_file = os.path.abspath(options.source_file)
else:
    globalvar.source_file = 'source_file.dat'

# Load the source_file
make_plots.source_dict = vm.read_control_file(globalvar.source_file)

# Load data used in other sections
print 'Loading supplementary data'
# Prefix extras files with main extras directory
for key in extras_dict.keys():
    extras_dict[key] = os.path.join(extras_dir, extras_dict[key])
vm.load_extra_data(extras_dict)

# Get the names of the experiment and control keys for the RMS table.
# This is a bit of a fudge and needs sorting out.
exper_key = make_plots.source_dict.keys()[0]
control_key = make_plots.source_dict.keys()[1]
for key in make_plots.source_dict.keys():
    if key[0] == 'e':
        exper_key = key
    if key[0] == 'c':
        control_key = key

# Initialise the rms list and title type
rms_list = rms.start(make_plots.source_dict[exper_key]['jobid'][0],
                     make_plots.source_dict[control_key]['jobid'][0])

# Set the page title
temp_dir = os.path.join(os.environ['SCRATCH'], 'valnote_temp')
with open(os.path.join(temp_dir, 'page_title.txt'), 'r') as f:
    page_title = f.read()

# Get the title type
make_plots.title_type = '4up'
if 'type' in globalvar.plots_dict[page_title]:
    make_plots.title_type = globalvar.plots_dict[page_title]['type'][0] 

# Get the equations
equation_dict = {}
for key in sorted(globalvar.plots_dict[page_title].keys()):
    if len(key) == 1:
        # Get the equation for the plot from the dictionary
        equation = globalvar.plots_dict[page_title][key][0:-1]
        equation_dict[key] = equation

# Make an array of locations
if len(equation_dict) == 1:
    location_dict = {'a': 111}
if len(equation_dict) == 2:
    location_dict = {'a': 121, 'b': 122}
if len(equation_dict) == 3:
    location_dict = {'a': 221, 'b': 222, 'c': 223}
if len(equation_dict) == 4:
    location_dict = {'a': 221, 'b': 222, 'c': 223, 'd': 224}
if len(equation_dict) >= 5 and len(equation_dict) <= 9:
    location_dict = {'a': 331, 'b': 332, 'c': 333, 'd': 334, 'e': 335,
                     'f': 336, 'g': 337, 'h': 338, 'i': 339}

# Export some global variables to the make_plots module for later
make_plots.title_dict = title_dict
make_plots.obs_dict = obs_dict
make_plots.rms_list = rms_list

# Loop through all the plots on the page
for key in sorted(location_dict.keys()):

    # Load the pickle file
    pickle_file = os.path.join(temp_dir, key+'.pkl')
    toplot_cube = vm.load_pickle(pickle_file)

    # Determine the plot type
    print 'Plotting plot number '+key
    globalvar.plot_type = vm.plot_type_test(toplot_cube[0])

    # If this is the first plot then define the page
    if key == 'a':
        make_plots.define_page(page_title, num_plots=len(equation_dict))

    if globalvar.plot_type in ('y_pressure', 'y_height', 'lat_lon', 'lat_lon_regional'):
        make_plots.contour_plot(toplot_cube, location_dict[key], page_title,
                                key, equation_dict[key], 'blank_file.png')
    elif globalvar.plot_type in ('x_longitude', 'x_latitude'):
        make_plots.line_plot(toplot_cube, location_dict[key], page_title,
                             key, equation_dict[key], 'blank_file.png')
    else:
        print 'Error determining plot type'

# Show the plot
if options.format != 'screen':
    filename = 'test_colours_out.'+options.format
    print 'Outputting to file '+filename
    plt.savefig(filename)
else:
    plt.show()