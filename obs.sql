CREATE TABLE IF NOT EXISTS obs (
  stID varchar NOT NULL,
  updated timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  file varchar DEFAULT NULL,
  source varchar NOT NULL,
  prio int unsigned NOT NULL,
  year int unsigned NOT NULL,
  month int unsigned NOT NULL,
  day int unsigned NOT NULL,
  hour int unsigned NOT NULL,
  minute int unsigned NOT NULL,
  timePeriod int unsigned DEFAULT NULL,
  timeSignificance int DEFAULT NULL,
  CONSTRAINT uniq_obs PRIMARY KEY (stID,year,month,day,hour,minute,timeSignificance,timePeriod,prio)
);
