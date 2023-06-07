#!/venv/bin/python3
#TODO: write bug report concerning memory leak to software.support@ecmwf.int

#decode bufr and save obs to database

#file lookup
from glob import glob
#sleep(seconds) function
from time import sleep
import numpy as np
#import pandas as pd
#python MySQL connector
#import MySQLdb
#regular expressions
import re
#for slicing dicts
#from itertools import islice
from datetime import datetime as dt, timedelta as td
#filesystem operations
from shutil import move, copyfileobj, copyfile
#read ini files
import configparser
#get command line arguments
import argparse
#bufr decoder by ECMWF
import eccodes as ec
#system modules
import psutil, os, sys
#writing dictionary to file, read it
import json
from write_files import write
from functions import total_size

#read config file
#config = configparser.ConfigParser()		
#config.read("config.ini")
#print(config)

#parser = argparse.ArgumentParser()

date = dt.now()
print( "ecdecode.py started @", date.strftime("%Y/%m/%d %H:%M") )

# Open database connection
#db = MySQLdb.connect("localhost", "obs", "obs4data", "obs" )

# prepare a cursor object using cursor() method
#cur = db.cursor()

bufr_dir      = "bufr/"
processed_dir = bufr_dir + "processed/"
files         = glob( bufr_dir + "Z__C_EDZW_*GER*bin" )
#files         = glob( bufr_dir + "*bin" )
#files          = glob( bufr_dir + "/GMA/*bin" )
output        = "output/"
data_json     = "data.json"

#list of known problematic desriptors (no tables available, not used etc)
skip      = ["unexpandedDescriptors","stationNumber","blockNumber"]
#skip      = ["unexpandedDescriptors"]
null_vals = (2147483647, -1e+100, None, "None", "XXXX", {}, "", [])


def save_json(data, output= data_json ):
    #save DATA as JSON
    with open(output, 'w') as f:
        json.dump(data, f)

def write_output( INPUT=data_json, output_dir=output, mode="csv"):
    #write json data to file (csv or rpl)
    with open( INPUT ) as f:
        INPUT = json.load( f )
        write( INPUT, output_dir, mode="csv" )

clear = lambda keyname : re.sub( r"#[0-9]+#", '', keyname )
number = lambda keyname : int( re.sub( r"#[A-Za-z0-9]+", "", keyname[1:]) )
to_key = lambda number, clear_key : "#" + str(number) + "#" + clear_key


times = []
timekeys = ['year','month','day','hour','minute','timePeriod','timeSignificance','timeIncrement']
DATA = {}

#files = [bufr_dir + "Z__C_EDZW_20220730105700_bda01,synop_bufr_GER_999999_999999__MW_870.bin"]

attrs = ('code', 'units', 'scale', 'reference', 'width')

n_files = 0
n_loops = 0

stations = []
station_names = []

for FILE in files[:10]:

    time_start = dt.now()
    keys = []

    with open(FILE, "rb") as f:

        nums = []

        try:
            bufr = ec.codes_bufr_new_from_file(f)
            if bufr is None: continue
            ec.codes_set(bufr, "unpack", 1)
            iterid = ec.codes_bufr_keys_iterator_new( bufr )
        except: continue

        while ec.codes_bufr_keys_iterator_next( iterid ):
            
            #store keynames
            try: keyname = ec.codes_bufr_keys_iterator_get_name( iterid )
            except: continue
            key = clear(keyname)

            if "#" in keyname and key not in skip + timekeys:
                num = number(keyname)
                if num not in nums:
                    nums.append(num)
                if key not in keys:
                    keys.append(key)
        
        print(keys)

        #free memory
        ec.codes_keys_iterator_delete(iterid)

        for num in nums:
            
            #we need a station number + block number!
            try:
                short_station = ec.codes_get(bufr, to_key(num, "shortStationName"))
            except: short_station = None

            try:
                station_number = ec.codes_get(bufr, to_key(num, "stationNumber"))
            except:
                station_number = None
            
            try:
                station_name = ec.codes_get(bufr, to_key(num, "stationOrSiteName"))
                if station_name not in station_names:
                    station_names.append(station_name)
            except:
                if station_number in null_vals:
                    #print("no station name & number!")
                    print(short_station)
                else:
                    #print(f"{station_number} has no station name!")
                    station_name = np.copy(station_number)
            try:
                block_number   = ec.codes_get(bufr, to_key(num, "blockNumber"))
            except: block_number = None
            
            if short_station not in null_vals:
                station = "_" + str(short_station)
                TYPE = "SYNA"
                print(short_station, station_name)
            elif station_number not in null_vals:
                if block_number not in null_vals:
                    station = str(station_number + block_number * 1000)
                    while len(station) < 5:
                        station_number = "0" +  station
                    TYPE = "SYNO"
                else:
                    station = "00" + station_number
            else:
                continue

            if station not in null_vals and station not in stations:
                stations.append(station)

            try:
                timecode = ""
                for i in timekeys[:-3]:
                    code = ec.codes_get(bufr, to_key(num, i))
                    if code in null_vals:
                        break
                    code = str(code)
                    if len(code) < 2:
                        code = "0" + code
                    timecode += code
            except:
                print("error with timecode")
                continue

            if timecode in null_vals: continue
            
            date = timecode[:8]
            hour = timecode[-4:-2]
            mins = timecode[-2:]

            try:
                time = abs(int(ec.codes_get(bufr, to_key(num, timekeys[-3]))))
                unit = ec.codes_get(bufr, to_key(num, timekeys[-3]+"->units"))
                if time in list(null_vals) + [0] and mins == "00":
                    time = "1h"
                else:
                    if time >= 60 and unit == "min":
                        time //= 60
                        unit = "h"
                    time = str(time_period) + unit
            except:
                time = "1h" if mins == "00" else "0"

            try:
                time_signif = ec.codes_get(bufr, to_key(num, timekeys[-2]))
                if time_signif in null_vals: time_signif = 0
            except: print("No timeSignificance given")#; sys.exit()

            if date not in DATA:
                DATA[date]                            = {}
            if station not in DATA[date]:
                DATA[date][station]                   = {}
            if hour not in DATA[date][station]:
                DATA[date][station][hour]             = {}
            if mins not in DATA[date][station][hour]:
                DATA[date][station][hour][mins]       = {}
            if time not in DATA[date][station][hour][mins]:
                DATA[date][station][hour][mins][time] = {}

            for key in keys:
                try: val = ec.codes_get(bufr, to_key(num, key))
                except: continue
                if val not in null_vals:
                    DATA[date][station][hour][mins][time][key] = val
                    if key == "totalPrecipitationOrTotalWaterEquivalent":
                        print(key, val)
                        try:
                            time_period = ec.codes_get(bufr, to_key(num, timekeys[-3]))
                            if time_period not in null_vals:
                                time_period = None
                                print(timekeys[-3], time_period)
                        except: pass
                else:
                    DATA[date][station][hour][mins][time][key] = None
                DATA[date][station][hour][mins][time]["type"] = TYPE 
                #try: print( ec.codes_get(bufr, to_key(num, key+"->percentConfidence") ) )
                #except: print("No percentConfidence!")

                #for attr in attrs:
                #    try: print( ec.codes_get(bufr, to_key(num, key+"->"+attr)) )
                #    except: print( attr + " not found!" )
                #    try:
                #        print( ec.codes_get(bufr, to_key(num, key+"->percentConfidence->"+attr)) )
                #    except: print( "percentConfidence of " + attr + " not found!" )
            
            #if all keys where empty delete entry
            if DATA[date][station][hour][mins] == {}:
                del DATA[date][station][hour][mins]

        f.close()
        n_files += 1

    n_loops += 1

    time_end = dt.now()
    time_diff = float(str(time_end - time_start )[-9:])
    times.append(float(time_diff))
    
    #move file to processed folder
    #move( FILE, processed_dir + FILE.replace(bufr_dir, "") )
    ec.codes_release(bufr)

    #free memory allocated by last bufr file
    #TODO: FIX MEMORY LEAK!
    process = psutil.Process(os.getpid())
    memory_used = process.memory_info().rss // 1024**2
    memory_free = psutil.virtual_memory()[1] // 1024**2 
    
    #only in first loop
    if n_loops == 1:
        memory_init = np.copy(memory_used)
  
    """
    os.system("clear")
    if len(times) > 0:
        print("READING...")
        print("max:    %1.3f s" % np.round( np.max(times), 3) )
        print("min:    %1.3f s" % np.round( np.min(times), 3) )
        print("mean:   %1.3f s" % np.round( np.mean(times), 3) )
        print("median: %1.3f s" % np.round( np.median(times), 3) )    
    
    print("\nMemory init: %4d MB" % memory_init )
    print("Memory used: %4d MB" % memory_used )  # in megabytes
    print("Memory free: %4d MB" % memory_free )
    
    perc = int(np.round((memory_used / memory_free) * 100))
    bars = perc // 10
    square = u'\u25A0'
    print("|" + square*bars + " " * (10 - bars) + "| [%3d%%]" % perc )
  
    n_dates = len(DATA)
    print("\nDates prcsd: %7d" % n_dates )
    print("Files prcsd: %7d" % n_files )
    print("Loops prcsd: %7d" % n_loops )
    
    
    print("\nSize (DATA): %4d MB" % int(round(total_size(DATA) / 1024**2 )) )
    print("    (times): %4d MB" % int(round(total_size(times) / 1024**2 )) )
    print("     (keys): %4d MB" % int(round(total_size(keys) / 1024**2 )) )
    print("     (nums): %4d MB" % int(round(total_size(nums) / 1024**2 )) )
    """

    #TODO: remove this nasty workaround after memory leak is fixed!
    #if less than 1 GB free memory: save output and restart program
    if memory_free <= 1024:
        print("Too much RAM used!")
        print("Last file:", FILE)
        
        save_json( DATA )
        write_output()
        
        #restart program
        exe = sys.executable
        os.execl(exe, exe, * sys.argv)
        sys.exit()


#print("%d files decoded" % len(files) )

#print(stations)
#print(station_names)

#save DATA as JSON
save_json( DATA )

#print("writing data...")
#write_output()
#print("writing finished!")

#db.commit()
#cur.close()
#db.close()