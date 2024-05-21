# What is OBS processing?
This repository contains everything needed to process and store synoptic observations from a variety of sources. Out-of-the box it supports DWD, KNMI and IMGW Open Data services and can parse BUFR files from many other providers.
It is easily extendable via configuration (YAML) files and by adding your own scripts which make use of the existing framework.
<br/><br/>

# How to install OBS processing
- Run install.sh like this:\
`chmod +x install.sh && ./install.sh`
- OR if the permissions cannot be set/changed:\
`bash install.sh`
- The install.sh script will install miniconda if not present, create an environment with all necessary packages and install the plbufr package from github as well as the local directory "package" using "python setup.py install".
- It then defines ".githook/" as the directory for git hooks. There is currently only one git hook which automatically compiles alls .py files before each commit, so at least some syntax errors can be easily avoided. It also exports the conda environment information to "config/environment.yml".
- Afterwards, it will compile all .py files in the directory in order to speed-up the first run of each script.
- Lastly, it executes 2 .sql files which add some essential tables and columns to the main database. These changes should be implemented in amalthea/main for a better integration.
<br/>

# How to use OBS processing

## Python scripts
All python scripts offer a -h/--help option which shows their command line arguments with a brief explanation. However, in order to understand them better, you should read the following in-depth information carefully.

### Note on command line arguments

All command line arguments are defined in "config/parser\_args.yml" and they are **the same across all scripts**. The only difference lies in their availability.\
For more details on adding/changing/removing command line arguments, please read the respective section about the **YAML configuration file** (parser\_args.yml).\
**IMPORTANT**: Settings defined by command line arguments always _overwrite_ settings defined in the script's configuration!
<br/><br/>
 
#### Common command line arguments

##### -h/--help
- show help message (defined in last column of "config/parser\_args")
##### -v/--verbose
- print (more) verbose output
##### -d/--debug
- run in debug mode with additional debug prints and stop points (using pdb module)
##### -t/--traceback
- use traceback module to print error messages that occur on module level
##### -w/--no\_warnings
- supress all warning messages
##### -i/--pid\_file
- use a PID file to determine whether the script is already running and which processes number it has
##### -l/--log\_level $LOG\_LEVEL
- define logging level (choose one of the following: {CRITICAL,ERROR,WARNING,INFO,DEBUG,NOTSET} )
##### -C/--config\_file $FILE\_NAME
- define a custom config file (has to be within "config/" directory)
##### -k/--known\_stations $LIST\_OF\_STATIONS
- comma-seperated list of stations to consider
##### -c/--clusters $LIST\_OF\_CLUSTERS
- comma-seperated list of clusters to consider
##### -m/--max\_retries $RETRIES
- maximal number of retries when writing to station databases
##### -n/--max\_files $NUMBER\_OF\_FILES
- maximal number of files to process (usually this setting applies per source)
##### -m/--mode $MODE
- operation mode (can be "dev", "oper" or "test")
##### -s/--stage $STAGE
- stage of forging (can be "raw","forge","bad" or "final")
##### -o/--timeout $TIMEOUT
- timeout in seconds when trying to write to station databases
##### -O/--output $OUTPUT\_PATH
- define custom output path where the station databases will be saved
##### -P/--processes $NUMBER\_OF\_PROCESSES
- use multiprocessing if -P > 1; defines number of processes to use
##### -T/--translation $TRANSLATION\_FILE
- define name of custom (BUFR) translation file (can be necessary for providers which use special encoding or error treatment)
<br/>
  
### decode\_bufr.py
This script decodes one or several BUFR files and inserts all relevant observations into the raw databases.\
It can also process intire source/dataset directories which can be provided by the source name as arguments or via the "source.yml" configuration file.\
To run the scripts, the configuration files "general.yml", "sources.yml" and "clusters.yml" are needed. So right before the first usage, you need to make sure to create them by copying the template files named "{file\_name}\_template.yml" to "config/" and adding your desired configurations/sources/clusters.

#### Unique command line arguments

##### source
- first and only positional argument
- can take several sources, seperated by spaces

##### -a/--approach $APPROACH
You may use 5 different approaches to decode the files:
- pd: Using pdbufr package officially provided by ECMWF (very slow because it uses pandas)
- pl: Using plbufr package forked from pdbufr by sferics (faster because it uses polars instead)
- gt: Also using plbufr bufr but instead of creating a dataframe it uses a generator (equally fast)
- us: Fastest decoding method using bufr keys from ECCODES but lacking some observations like soil temperatures
- ex: Slower than "us" method but significantly faster than pdbufr/plbufr methods. Not guaranteed to work with all files and lacking some information from DWD Open Data files
##### -f/--file $FILE\_PATH
- process a single file, given by its file path
##### -F/--FILES $LIST\_OF\_FILES
- process several files, given by their file paths, seperated by divider character (default: ";")
##### -D/--divider $DIVIDER
- define a custom divider/seperator character for -F
##### -r/--redo
- process file(s) again, even if they have been processed already
##### -R/--restart
- usually only used automatically by the script if the RAM is full, so it knows which files are still left to process
##### -s/--sort\_files
- sort files with sorting algorithm (sorted() by default)
##### -H/--how
- define sorting algorithm for the above option (has to be a python callable and will be evaluated by eval() method)

#### Example usages

##### single file, redo even if already processed:
`decode_bufr.py -a pl -f example_file.bufr -r`

##### multiple files, use "," as divider character, show verbose output:
`decode_bufr.py -a ex -F example_file1.bin,example_file2.bin,example_file3.bin -D "," -v`

##### single source, consider only specific stations:
`decode_bufr.py DWD -a gt -k 10381,10382,10384,10385`

##### multiple sources, process a maximum of 100 files per source:
`decode_bufr.py DWD KNMI RMI -a gt -n 100`

##### custom config file, process all sources which are defined there and use custom output directory:
`decode_bufr.py -C obs_custom.yml -O /custom/output/directory`
<br/><br/>
 
### forge\_obs.py
This is a chain script which runs the following scripts in the order of occurrence. Only in operational mode, derived\_obs.py runs again after aggregate\_obs.py and export\_obs.py will only be executed if -e/--export is set.

#### Unique command line arguments
##### -b/--bare
- only print out commands and do not actually run the scripts
- this is meant for debugging purposes only
##### -e/--export
- export new observations into old/legacy metwatch csv format after finishing the chain (see export\_obs.py for more information)
##### -L/--legacy\_output $LEGACY\_OUTPUT
- define old/legacy metwatch csv output directory for export\_obs.py

#### Example usage
##### Define custum output path and set log level to "INFO"
`python forge_obs.py -e -L /legacy/output/path -l INFO`
<br/><br/>
 
> ### reduce\_obs.py
> (only 1 row with max(file) per dataset [UNIQUE datetime,duration,element])
> Copy all remaining elements from raw to forge databases [dataset,datetime,duration,element,value]
> 
> #### Example usage
> ##### Use 12 processes:
> `python reduce_obs.py -P 12`
> <br/><br/>
> 
> ### derive\_obs.py
> Compute derived elements like relative humidity, cloud levels or reduced pressure from (a combination of) other elements.
> 
> #### Unique command line arguments
> ##### -A/--aggregated
> Compute derived elements again, but only considering 30min-values.
> 
> #### Example usage
> ##### Only derive observations from a single station:
> `python derive_obs.py -k 10381`
> <br/><br/>
> 
> ### aggregate\_obs.py
> Aggregate over certain time periods / durations (like 30min,1h,3h,6h,12,24h) and create new elements with "\_{duration}" suffix.
> The information about what elements to aggregate over which durations is contained in "config/element\_aggregation.yml".
>  
> #### Example usage
> ##### Enable traceback prints
> `python aggregate_obs.py -t`
> <br/><br/>
> 
> ### audit\_obs.py
> Check all obs in forge databases, delete bad data like NaN, unknown value or out-of-range
> - move good data in final databases e.g. "/oper/final" (oper mode)
> - move bad data to seperate databases, e.g. "/dev/bad" (dev mode)
> 
> #### Example usage
> #### Run in debugging mode with debug prints and stop points
> `python audit_obs.py -d`
> <br/><br/>
> 
> ### empty\_obs.py
> Clear forge station databases (they are temporary and get rebuilt every chain cycle).
> 
> #### Unique command line arguments
> ##### -B/--bad\_obs
> - clear bad obs as well
> #### Example usage
> ##### Use the above option and show no warnings
> `python empty_obs.py -B -w`
> <br/><br/>
> 
> ### export\_obs.py
> Export observations from final databases into the old/legacy metwatch csv format.
> 
> #### Unique command line arguments
> ##### -L/--legacy\_output $LEGACY\_OUTPUT
> - define old/legacy metwatch csv output directory
> #### Example usage
> ##### Define a custom directory for the legacy output
> `python export_obs.py -L /legacy/output/directory`
> <br/><br/>

### get\_imgw.py
Get latest observations from the Polish Open Data service
#### Example usage
##### Verbose output and consider only stations in cluster "poland"
`python get_imgw.py -v -c poland`
<br/><br/>

## Description of YAML files and structure in "config/" directory

### codes/
> #### bufr/
> > ##### flags_{approach}.yml
> > \- conversion of BUFR code/flag tables into values we use
> > ##### sequences.yml
> > \- definition of wmo BUFR sequences
> > \- only needed for "ex" approach of decode\_bufr.py
> ##### synop.yml
> \- conversion of SYNOP codes into values we use
> ##### metar.yml
> \- conversion of METAR codes into values we use

##### element\_aggregation.yml
\- information about which element to aggregate OR fill in gaps
\- consists of two sections:
> **duration:**
> \- which element to aggregate over which durations
> \- fallback elements can be defined (like TMP instead of TMAX)
> **instant:**
> \- which elements always have the same duration
> \- for these elements we try to fill in the gaps (use nearby values)

##### element\_info.yml
\- information about the value range of elements (lower/upper boundaries)
\- also: which values to include or exclude out of that range (extra/exclude)
\- extra column is a list of values and these will always be excepted, even if they are out-of-range
\- exclude is defined as a regular expression (x means no exluded values)
\- used for audit\_obs.py script only

##### environment.yml
\- conda environment information (environment name, packages to install, conda settings)\
\- does not contain prefix and variables because they are system-dependent

##### general\_template.yml
\- needs to be copied to "config/general.yml" in order to be recognized by the python scripts
\- main configuration file template with the following sections:

> **general:**\
> \- most general settings which will be overwritten by all following configs\
> \- order: general -> class -> script -> command line arguments\
> **database:**\
> \- configuration for the main database (usually when DatabaseClass is called for main.db)\
> **bufr:**\
> \- configuration for the BufrClass\
> **obs:**\
> \- configuration for the ObsClass\

##### scripts.yml
\- just change the settings of all scripts to your desire in here
\- sections/keys are always the FULL script name (with .py)!
\- some important script configurations in detail:
> **decode_bufr.py:**\
> \- TODO\
> **forge_obs.py:**\
> \- TODO\
> **aggregate_obs.py:**\
> \- TODO\
> **get_imgw.py:**\
> \- TODO\
> **get_knmi.py:**\
> \- TODO\

##### sources\_template.yml
\- needs to be copied to "config/sources.yml" in order to be recognized by the python scripts
##### clusters\_template.yml
\- needs to be copied to "config/clusters.yml" in order to be recognized by the python scripts

### translations/
> #### bufr/
> > ##### {approach}.yml
> > \- BUFR key translations for the different approaches
> ##### metwatch.yml
> \- translation for the legacy metwatch element names
> ##### imgw.yml
> \- translation for element names of Polish weather service Open Data
> ##### {other\_source}.yml
> \- use this naming scheme if you want to add your own custom source translation files

##### parser\_args.yml
\- definition of positional and flag (e.g. -v/--verbose) command line arguments 
### station\_tables/
> ##### {mode}\_{stage}.yml
> \- definition of the table structure for the location/station databases
> \- the syntax is very SQL-like but simpler than a real .sql file
> \- different mode and stage combination need to be all present if you add custom modes/stages
<br/>

## Bash scripts in "scripts/" directory

### export\_bufr\_tables.sh
Export your custom BUFR table paths to the local and conda environment variables.
<br/>

### export\_conda\_environment.sh
Exports conda environment information to "config/enviroment.yml". Only skips "path:" and "variables:" section because they depend on the local system.
<br/>

### install.sh
Install the repository using conda and prepare everything to get started immediately. It creates the "obs" environment, installs all needed packages and sets the right environment variables.
<br/>

### multi\_decode\_bufr.sh
This scripts starts the decode\_bufr.py script multiple times, so you can process a large number of files much faster.\
NOTE: You have to calculate manually how many files to process for each instance of the script and define max\_files accordingly in the script config's "decode\_by.py:" section.
<br/>

#### Command line arguments
##### $1 $APPROACH
- set BUFR decoding approach (default: gt)
##### $2 $PROCESSES
- number of processes to use (start decode\_bufr.py N times)
##### $3 $SLEEP\_TIME
- sleep time in between script execution (wait N seconds before starting the next instance)

#### Example usage
##### Start 8 instances of decode\_bufr.py using "ex" approach and 2 seconds sleep time in between
`./multi_decode_bufr.sh 8 ex 2` 
