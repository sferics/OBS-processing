#!/usr/bin/env python
import os
from collections import defaultdict
import global_functions as gf
import global_variables as gv
import sql_factories as sf
from database import DatabaseClass as dc
from config import ConfigClass as cc
from obs import ObsClass as oc

#TODO HIGH PRIORITY! ESSENTIAL!

  #ClNCmNChN: [CLCMCH_2m_syn,  ~, 1, 0]  # Wolkenarten in den Stockwerken                   (zB: Cu2Ac3Cs6) -> 236
  #ClNCmNChN: [CLCMCH_2m_syn,  ~, 1, 0]  # -> Wolkenmenegen in den Stockwerken              (zB: 3451, 1///)
  #NC1XXX:    [CL1_2m_syn,     ~, 1, 0]  # unterste Wolkenschicht Bedeckung/Art/Untergrenze (zB: 2ST020) -> 2020
  #NC2XXX:    [CL2_2m_syn,     ~, 1, 0]  # 2.Wolkenschicht                                  (zB: 4AC100) -> 4100
  #NC3XXX:    [CL3_2m_syn,     ~, 1, 0]  # 3.Wolkenschicht                                  (zB: 5CS300) -> 5300
  #NC4XXX:    [CL4_2m_syn,     ~, 1, 0]  # 4.Wolkenschicht                                  (zB: 2CB080) -> 2080
  #NC1XXX:    [CL?_2m_syn,     ~, 1, 0]  # Wolkenschicht Bedeckung+Untergrenze              (zB: 1015, 5300, 2080)

#TODO if no TCC_LC_syn: take TCC_ceiling_syn

#TODO derive total cloud cover per height level (CL, CM, CH)

#TODO derive cloud layers (CL_?) from cloud bases and cloud amounts

# only in station_test: first devide cloud height by 30

# CL?_2m_syn = TCC_?C_syn + CB?_2m_syn
# if no TCC_[1-3]C_syn present:
# CL1_2m_syn = CDCL_2m_syn + CB1_2m_syn
# CL2_2m_syn = CDCM_2m_syn + CB2_2m_syn
# CL3_2m_syn = CDCH_2m_syn + CB3_2m_syn

#TODO derive VIS_2m_syn from MOR_2m_syn, MOR_2m_min, MOR_2m_max, VIS_2m_min, VIS_2m_pre, VIS_2m_run, VIS_2m_sea
# if no VIS_2m_syn: VIS_2m_syn = MOR_2m_syn
# [if no VIS_2m_syn and no MOR_2m_syn: VIS_2m_min, MOR_2m_min, VIS_2m_pre, VIS_2m_run, VIS_2m_sea, MOR_2m_max (priorities)]

# if key is not found, try to take replacements[key], else ignore

def derive_obs(stations):
    
    for loc in stations:

        sql_values = set()
        
        db_file = f"{output}/forge/{loc[0]}/{loc}.db"
        try: db_loc = dc( db_file, row_factory=sf.list_row )
        except Exception as e:
            gf.print_trace(e)
            if verbose:     print( f"Could not connect to database of station '{loc}'" )
            if traceback:   gf.print_trace(e)
            continue
        
        if source in {"test", "DWD", "dwd_germany"}:
            # in DWD data we need to replace the duration for 9z Tmin/Tmax obs
            sql = "UPDATE OR IGNORE obs SET duration='15h' WHERE element IN('TMAX_2m_syn','TMIN_2m_syn','TMIN_5cm_syn') AND strftime('%H', datetime) = '09'"
            #sql = "UPDATE OR IGNORE obs SET duration='1s' WHERE element LIKE 'CB%_2m_syn'"
            #sql = "UPDATE OR IGNORE obs SET element='TCC_1C_syn' WHERE element='TCC_ceiling_syn'"
            try:    db_loc.exe(sql)
            except: continue
            else:   db_loc.commit()

        """
        sql1="SELECT datetime,duration,element,value FROM obs WHERE element = '%s'"
        sql2="INSERT INTO obs (datetime,duration,element,value) VALUES(?,?,?,?) ON CONFLICT IGNORE"

        found = False

        for replace in replacements:
            print(replace)
            replace_order = replacements[replace].split(",")
            for i in range(len(replace_order)):
                #if found: break
                db_loc.con.row_factory = sf.list_row
                db_loc.exe(sql1 % replace_order[i])
                #print(sql1 % replace_order[i])
                data = db_loc.fetch()
                #if data: found = True
                for j in data:
                    print(j)
                    j[2] = replace
                    print(j)
                    sql_values.add( tuple(j) )

        print(sql_values)
        db_loc.exemany(sql2, sql_values)
        """    
    
        sql = "SELECT datetime,element,round(value) from obs WHERE element IN ('CDC{i}_2m_syn', 'CB{i}_2m_syn') ORDER BY datetime asc, element desc"
        
        # https://discourse.techart.online/t/python-group-nested-list-by-first-element/3637

        sql_values = set()

        for i in range(1,5):
            #print(sql.format(i=i))
            db_loc.exe(sql.format(i=i))
            data = db_loc.fetch()
            
            CL              = defaultdict(str)
            cloud_covers    = set()

            for j in data:
                if len(CL[j[0]]) == 0 and j[1] == f"CDC{i}_2m_syn" and j[0] not in cloud_covers:
                    CL[j[0]]    += str(int(j[-1]))
                    cloud_covers.add(j[0])
                elif len(CL[j[0]]) == 1 and j[1] == f"CB{i}_2m_syn" and j[0] in cloud_covers:
                    CL[j[0]]    += str(int(j[-1])).rjust(3,"0")

            CL = dict(CL)

            for k in CL:
                if len(CL[k]) == 1:
                    CL[k] += "///"
                sql_values.add( (k, f"CL{i}_2m_syn", CL[k]) )
        
        # duration is always 1s for cloud observations
        sql = "INSERT INTO obs (datetime,element,value,duration) VALUES(?,?,?,'1s') ON CONFLICT DO UPDATE SET value=excluded.value" #NOTHING"
        try:    db_loc.exemany(sql, sql_values)
        except: continue

        # https://stackoverflow.com/a/49975954
        sql = "DELETE FROM obs WHERE length(value) > 4 AND element LIKE 'CL%_2m_syn'"
        try:    db_loc.exe(sql)
        except: continue
        
        #TODO medium priority, nice-to-have...

        #TODO try to calculate QFF and QNH if no reduced pressure is present in obs and we have barometer height instead
        db = dc( config=cf.database, ro=1 )
        
        #TODO we should actually prefer the barometer elevation over general elevation because they can differ a lot
        baro_height = db.get_station_baro_elev(loc)
        
        if baro_height is None:
            baro_height     = db.get_station_elevation(loc)
            station_height  = copy(baro_height)
        else:
            station_height  = copy(baro_height)
            baro_height     = db.get_station_baro_elev(loc)

        db.close()
        
        ##TODO MEDIUM priority, could be useful for some sources
        
        # derive [PRATE_1m_syn, TR] from PRATETR_1m_syn and TR
        
        # get all datetime where both elements are present and have a NOT NULL value
        
        sql = ("SELECT DISTINCT datetime FROM obs WHERE element = 'PRATE_1m_syn' AND "
            "value IS NOT NULL JOIN SELECT DISTINCT datetime FROM obs WHERE element = 'TR' "
            "AND value IS NOT NULL")
        db_loc.exe(sql)
        
        sql_insert  = "INSERT INTO obs datetime,element,value,duration VALUES (?,'PRATE_1m_syn',?,?)"
        prate_vals  = set()

        for datetime in db_loc.fetch():
            
            sql = (f"SELECT value FROM obs WHERE datetime = '{datetime}' AND element IN "
                f"('PRATE_1m_syn', 'TR') ORDER BY element")
            
            db_loc.exe(sql)
            
            for values in db_loc.fetch():
                prate   = values[0]
                tr      = values[1]
                prate_vals.add( (datetime, prate, tr) )
        
        db_loc.exemany(sql_insert, prate_vals)
        

        # derive reduced pressure (QFF or QNH?) if only station pressure was reported
         
        if baro_height is not None:
            
            db  = dc( config=cf.database, ro=1 )
            lat = db.get_station_latitude()
            db.close()

            # first get all datetimes where there is no PRMSL recorded but PRES (30min values only)

            sql = (f"SELECT DISTINCT datetime FROM obs WHERE strftime('%M', datetime) IN "
                f"('00','30') AND element LIKE 'PRES_0m_syn' AND value IS NOT NULL JOIN "
                f"SELECT DISTINCT datetime FROM obs WHERE strftime('%M', datetime) IN "
                f"('00','30') AND element LIKE 'PRMSL_ms_%' AND IFNULL(value, '') = ''")
                #AND value IS NULL OR value = ''
            
            db_loc.exe(sql)
            
            datetimes = set( db_loc.fetch() )
           
            sql_insert  = "INSERT INTO obs datetime,element,value,duration VALUES (?,?,?,1s)"
            prmsl_vals  = set()

            # try calculate PRMSL for all datetimes where only PRES is available
            sql = (f"SELECT datetime,value FROM obs WHERE element = 'PRES_0m_syn'")
            
            db_loc.exe(sql)

            for row in db_loc.fetch():
                datetime    = row[0]
                value_PRES  = row[1]
                
                # we prefer to use qff, so try to get all needed elements for it 
                sql = (f"SELECT value FROM obs WHERE element IN ('TMP_2m_syn', 'DPT_2m_syn', "
                    f"'RH_2m_syn') AND datetime = '{datetime}' ORDER BY element")
                
                db_loc.exe(sql)
                
                values      = db_loc.fetch()
                value_DPT   = values[0]
                value_RH    = values[1]
                value_TMP   = values[2]
                
                #if station and baro height differ: calculate QFE
                #if station_height != baro_height:
                #   qfe = gf.qfe(value_PRES, baro_height-station_height)
                
                if value_PRES is not None and value_TMP is not None and baro_height <= 350:
                    pr_qnh = gf.qnh( value_PRES, baro_height, value_TMP )
                    prmsl_vals.add( datetime, "PRMSL_ms_met", pr_qnh )
                    
                    # if dewpoint or relative humidity are present: use DWD reduction method
                    #https://www.dwd.de/DE/leistungen/pbfb_verlag_vub/pdf_einzelbaende/vub_2_binaer_barrierefrei.pdf?__blob=publicationFile&v=4 [page 106]
                    if value_DPT is not None or value_RH is not None and baro_height < 750:
                        
                        if value_DPT is not None:
                            value_RH = gf.dpt2rh(value_DPT, value_TMP)
                        
                        pr_qff  = gf.qff( value_PRES, baro_height, value_TMP, value_RH )
                        prmsl_vals.add( datetime, "PRMSL_ms_syn", pr_qff )
                
            db_loc.exemany(sql_insert, prmsl_vals)
            

            #TODO calculate derivation of dewpoint temperature here, add unit conversions...
            """
            dp = "dewpointTemperature"; dp2 = "dewpointTemperature2m"
            T = "airTemperature"; T2 = "airTemperatureAt2m"; rh = "relativeHumidity"

            # if we already has the dewpoint temperature at 2m height, skip!
            if dp2 in obs or (dp in obs and sensor_height[0] == 2):
                pass
            elif rh in obs and ( (T in obs and sensor_height[0] == 2) or T2 in obs ):
                if T in obs: T = obs[T][0]
                else: T = obs[T2][0]
                rh = obs[rh][0]

                obs[dp2] = ( gf.rh2dpt( rh, T ), "2s" )
            """
            


            ##TODO LOW priority, not really needed at the moment
            
            #TODO take 5m wind as 10m wind if 10m wind not present (are they compareble???)
            
            #TODO derive wind direction from U and V
            
            #TODO derive total sunshine duration in min from h
            #TODO derive total sunshine duration in min from % (using astral package; see wetterturnier)
            
            #TODO derive precipitation amount from duration and intensity
            # (might be necessary to aggregate)
            
             
        db_loc.close(commit=True)

    return


if __name__ == "__main__":
    
    # define program info message (--help, -h)
    info        = "Derive obs elements from other parameters"
    script_name = gf.get_script_name(__file__)
    flags       = ("l","v","C","m","M","o","O","d","t","P")
    cf          = cc(script_name, pos=["source"], flags=flags, info=info, verbose=True)
    log_level   = cf.script["log_level"]
    log         = gf.get_logger(script_name, log_level=log_level)
    start_time  = dt.utcnow()
    started_str = f"STARTED {script_name} @ {start_time}"

    log.info(started_str)

    # define some shorthands from script config
    verbose         = cf.script["verbose"]
    debug           = cf.script["debug"]
    traceback       = cf.script["traceback"]
    timeout         = cf.script["timeout"]
    max_retries     = cf.script["max_retries"]
    mode            = cf.script["mode"]
    output          = cf.script["output"] + "/" + mode
    clusters        = cf.script["clusters"]
    stations        = cf.script["stations"]
    processes       = cf.script["processes"]
    replacements    = cf.script["replacements"]
    combinations    = cf.script["combinations"]

    obs             = oc( cf, source, stage="forge" )
    db              = dc( config=cf.database, ro=1 )
    stations        = db.get_stations( clusters )
    db.close(commit=False)

    if processes: # number of processes
        import multiprocessing as mp
        from random import shuffle
        import numpy as np

        stations = list(stations)
        shuffle(stations)
        #stations_groups = gf.chunks(stations, processes)
        station_groups = np.array_split(stations, processes)

        for station_group in station_groups:
            p = mp.Process(target=derive_obs, args=(station_group,))
            p.start()

    else: derive_obs(stations)
