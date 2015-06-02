#!/usr/bin/env python

import datetime
import warnings
import numpy as np
import os
import sys
import math
import time
import fnmatch
import netCDF4 as nc
import matplotlib as mpl
mpl.use( 'Agg' )				##necessary when there is no xserver avail
import matplotlib.pyplot as plt



############## config ####################
dscovr_mission_start = datetime.datetime(2015, 02, 15)
dscovr_file_base = '/nfs/dscovr_private/'
dscovr_plot_output_base = '/nfs/dscovr_private/plots/'

dscovr_ts_width = 14 	#inches
dscovr_ts_height = 10 	#inches
dscovr_ts_frame_sizes = [
	#name		#path				#filename	#startms		#finishms
	["6hour1",	"dscovr_6hr_plots/%Y/%m",	"%Y%m%d00-6hr", 0,			1000 * 60 * 60 * 6],
	["6hour2",	"dscovr_6hr_plots/%Y/%m",	"%Y%m%d06-6hr", 1000 * 60 * 60 * 6, 	1000 * 60 * 60 * 12],
	["6hour3",	"dscovr_6hr_plots/%Y/%m",	"%Y%m%d12-6hr", 1000 * 60 * 60 * 12, 	1000 * 60 * 60 * 18],
	["6hour4",	"dscovr_6hr_plots/%Y/%m",	"%Y%m%d18-6hr", 1000 * 60 * 60 * 18, 	1000 * 60 * 60 * 24],
	["1day",	"dscovr_1day_plots/%Y/%m",	"%Y%m%d-day", 	0,			1000 * 60 * 60 * 24],
	["3day",	"dscovr_3day_plots/%Y/",	"%Y%m%d-3day", 	0,			1000 * 60 * 60 * 24 * 3],
	["7day",	"dscovr_7day_plots/%Y/",	"%Y%m%d-7day", 	0,			1000 * 60 * 60 * 24 * 7],
	["1month",	"dscovr_month_plots/%Y/",	"%Y%m-month", 	0,			0] #month is going to to take a custom range, months not all same length
]

dscovr_ts_pane_config = [
	# Y axis label		#[quiet scale, storm scale]	#line config [ ["file", "datatype", "label", "style"], ["file", "datatype", "label", "style"] ]
								# file is the file in which datatype is found
				#if max data point is above	# datatype corresponds to what is in the netcdf file
				#quiet scale, max, it will 	# label is what will show up in the legend
				#switch and use storm scale	# leave label empty "" for no legend
	["Pressure\n [nPa]",	[ [0,5], [0,10] ], 		[["m1m", "bz_gsm", "", "b-"]] ],
	["Mag\n [nT]",		[ [-20, 20], [-50,50] ], 	[["m1m", "bx_gsm", "Bx(gsm)", "r-"], ["m1m", "by_gsm", "By(gsm)", "g-"], ["m1m", "bz_gsm", "Bz(gsm)", "k-"]] ],
	["Mag\n [nT]",		[ [-20, 20], [-50,50] ], 	[["m1m", "bx_gsm", "Bx(gsm)", "r-"], ["m1m", "by_gsm", "By(gsm)", "g-"], ["m1m", "bz_gsm", "Bz(gsm)", "k-"]] ],
	["Speed\n [km/s]",	[ [200, 800], [200, 800] ], 	[["f1m", "alpha_speed", "Vsw DSCOVR", "b-"], ["f1m", "alpha_speed", "Vsw Bow", "k-"]] ],
	["Prop Time\n [min]",	[ [20, 100], [20, 100] ], 	[["f1m", "alpha_speed", "", "k-"]] ],
	["Temperature\n [K]",	[ [10e4, 10e6], [10e4, 10e6] ],	[["f1m", "alpha_temperature", "Temp DSCOVR", "k-"]] ], ##note temperature is hardcoded as semilogy scale
	["Density\n [cc]",	[ [0, 90], [0,90] ], 		[["f1m", "alpha_density", "Dens DSCOVR", "b-"], ["f1m", "alpha_density", "Dens Bow", "k-"]] ]
]

dscovr_ts_panes = len( dscovr_ts_pane_config )	#number of panes
##########################################


def find_file(dt, type):
	"""Since the processing time is unknown, use the type and the date to
	make a string like it_m1m_dscovr_s(date)_e(date)_p*_pub.nc and pattern match
	to fill in the processing date p*"""
	seek_path_piece = dscovr_file_base + dt.strftime("%Y/%m/")					##path under file base to look in
	seek_path_full = os.path.join( dscovr_file_base, seek_path_piece )
	seek_filename = dt.strftime("it_%%s_dscovr_s%Y%m%d000000_e%Y%m%d235959_p*_emb.nc") % type	##file name with * instead of processing date
	for root, dirs, files in os.walk( seek_path_full ):
		for name in files:
			if fnmatch.fnmatch( name, seek_filename ):
				return os.path.join( root, name )

def unix_time_millis(dt):
	epoch = datetime.datetime.utcfromtimestamp(0)
	delta = dt - epoch
	return delta.total_seconds() * 1000.

def startof_frame(dt, frame_type):
	if frame_type == "3day":
		ms_in_3_days = 1000 * 60 * 60 * 24 * 3
		mission_start_in_ms = unix_time_millis( dscovr_mission_start )
		dt_in_ms = unix_time_millis( dt )
		offset = dt_in_ms - mission_start_in_ms
		ms_of_period = mission_start_in_ms + ms_in_3_days * math.floor( offset / ms_in_3_days )
		return datetime.datetime.utcfromtimestamp( ms_of_period/1000 )
	elif frame_type == "7day":
		ms_in_7_days = 1000 * 60 * 60 * 24 * 7
		mission_start_in_ms = unix_time_millis( dscovr_mission_start )
		dt_in_ms = unix_time_millis( dt )
		offset = dt_in_ms - mission_start_in_ms
		ms_of_period = mission_start_in_ms + ms_in_7_days * math.floor( offset / ms_in_7_days )
		return datetime.datetime.utcfromtimestamp( ms_of_period/1000 )
	elif frame_type == "1month": ##this one is never actually used, included for completeness?
		return datetime.datetime( dt.year, dt.month, 1 )
	else:
		return dt
		

def make_plot(output_path): ##can only be called after dscovr_ts_pane_config has been filled out with data

	plt.figure( 0, figsize = [dscovr_ts_width, dscovr_ts_height] ) 		#new figure
	plt.clf()								#Clear the current figure

	dscovr_ts_pane_i = 1
	for pane_config in dscovr_ts_pane_config:
		plt.subplot( dscovr_ts_panes, 1, dscovr_ts_pane_i) 		#subplot(n rows, n cols, plot n)
		#print pane_config[2][0][4]
		dscovr_ts_domain = [ pane_config[2][0][4][:][0], pane_config[2][0][4][:][-1] ] ## <- crazy array accessor, gets beginning and end of time dimention
		plt.xlim( dscovr_ts_domain )
		plt.legend( prop={'size':7}, loc='upper left' )
		plt.ylabel( pane_config[0] )
		plt.grid( True )
		plt.locator_params(axis = 'y', nbins = 4)
		
		#title at top of figure
		if dscovr_ts_pane_i == 1: 
			plt.title( "DSCOVR : %s - %s" % (dscovr_ts_domain[0], dscovr_ts_domain[1]) )
	
		use_storm_scale = False

		##each stroke in the pane
		for stroke in pane_config[2]:

			#print "running plt.plot(%s, %s, %s, label=%s)" % (stroke[4], stroke[5], stroke[3], stroke[2])
			if pane_config[0] == "Temperature\n [K]":
				#plt.semilogy( stroke[4], stroke[5], stroke[3], label=stroke[2] ) ##TODO: uncomment this when the correct data is coming, complaining about log scale with no positive values right now
				pass
			else:
				plt.plot( stroke[4], stroke[5], stroke[3], label=stroke[2] )			#plot x, y, format

			try:
				if ( np.nanmax( stroke[5] ) > pane_config[1][0][1] ): # if max of data is greater than upper bound of quiet scale:
					use_storm_scale = True
			except ValueError: # handle no data here, just pass leaving use_storm_scale False
				pass
			stroke.pop(), stroke.pop() ##get rid of the time and data from the end of the stroke config (IMPORTANT/hacky so that next frame size iteration works)
		
		if use_storm_scale == False:
			plt.ylim( pane_config[1][0] )
		else:
			plt.ylim( pane_config[1][1] )

		##x axis labels
		if dscovr_ts_pane_i != dscovr_ts_panes:			#unless it's the last one
			plt.gca().set_xticklabels( [] )			#gca: get current axes, make so no ticks
		#else: 			##it seems like the default/auto does this best
			#ax = plt.gca()
			#ax.xaxis.set_major_locator( mpl.dates.HourLocator() )
			#ax.xaxis.set_major_formatter( mpl.dates.DateFormatter( '%H' ) )
			#ax.set_ylim( bottom=0 )
			
		dscovr_ts_pane_i += 1

	plt.savefig( output_path, bbox_inches='tight' )

def main(date):
	date_to_plot = date

	for frame_size in dscovr_ts_frame_sizes:							# loop over frame sizes defined
		print( "getting data for: %s" % frame_size[0] )
		frame_beginning = startof_frame( date_to_plot, frame_size[0] )				# only used if not 1month frame size

		for pane_config in dscovr_ts_pane_config:
			print( "\tpane: %s" % pane_config[0].split('\n')[0] )

			for stroke in pane_config[2]:
				#for multiple strokes on same pane, eg bz, bx, and by
				
				file_paths = []
				if frame_size[0] == "1month":
					##treated specially because nc.MFDataset can take * wildcard and files are stored
					## in the directories by month, so format the proper wildcard string for the datatype
					path_part = os.path.join( dscovr_file_base, date_to_plot.strftime("%Y/%m") )
					file_paths = path_part + "/it_" + stroke[0] + "_dscovr_*.nc" 
				else:
					##otherwise have to iterate by date to get the filenames containing the data for the period
					frame_beginning_millis = unix_time_millis( frame_beginning )
					start_millis = frame_beginning_millis + frame_size[3]
					end_millis = frame_beginning_millis + frame_size[4]
					
					current_get_millis = frame_beginning_millis
					while current_get_millis < end_millis:
						current_get = datetime.datetime.utcfromtimestamp( current_get_millis/1000 )
						#print( " 		trying date: %s" % current_get )
						path = find_file( current_get, stroke[0] )
						#print( " 		found: %s"% path )
						if path: 					#because nc.MFDataset can't handle a None
							file_paths.append( path )
						current_get_millis += 1000 * 60 * 60 * 24 	#increment by millisec in a day
				try:
					dataset = nc.MFDataset( file_paths )

					time = dataset.variables[ 'time' ][:] 					# type is np.ndarray, pull time from nc file
					data = dataset.variables[ stroke[1] ][:]				# pull out the data
					
					
					## filtering to make sure data in range, this is only necessary for 6hr plots			
					finaldata = [ x for i,x in enumerate(data) if time[i] > start_millis and time[i] < end_millis ]
					finaltime = [ datetime.datetime.utcfromtimestamp( x/1000 ) for x in time if x > start_millis and x < end_millis ]	# convert to datetimee

					stroke.append( finaltime ) 							# plug it into the config, see pop in the make_plot function
					stroke.append( finaldata )							# put it into the config as well, this is what second pop in make_plot is for
				except IndexError: ##handle the case when all the data is missing
					stroke.append( [[]] ) # we might want to do something different, but for now this will keep the program running 
					stroke.append( [[]] ) # and produce a blank plot
		
		##format path and filename, verify path exists
		plot_path = dscovr_plot_output_base + frame_beginning.strftime( frame_size[1] )
		if not os.path.exists( plot_path ):
			os.makedirs( plot_path )
		plot_filename = frame_beginning.strftime( frame_size[2] )
		out = os.path.join( plot_path, plot_filename )

		## Config now contains the data, so can call make_plot
		print "plotting %s\n" % out
		make_plot( out )

#get rid of some annoying warnings
if __name__ == "__main__":
	warnings.filterwarnings("ignore")
	try:
		date = datetime.datetime.strptime( str( sys.argv[1] ), "%Y%m%d")
		main(date)
	except (ValueError, IndexError):
		print( "Usage: python plotter.py <YYYYmmdd>" )
