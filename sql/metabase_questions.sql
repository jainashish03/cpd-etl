-- Paste each into Metabase: New > SQL query. Save, then add to a dashboard.

-- 1) Incidents per day, last 30 days (line)
SELECT incident_date, count(*) AS incidents
FROM cpd.daily_police_log
WHERE incident_date > (SELECT max(incident_date) FROM cpd.daily_police_log) - 30
GROUP BY 1
ORDER BY 1;

-- 2) Top offence types, last 30 days (bar)
SELECT regexp_replace(crime_description, '\s+C\d+[A-Z]?\s+S.*$', '') AS offence,
       count(*) AS incidents
FROM cpd.daily_police_log
WHERE crime_description IS NOT NULL
  AND incident_date > (SELECT max(incident_date) FROM cpd.daily_police_log) - 30
GROUP BY 1
ORDER BY 2 DESC
LIMIT 15;

-- 3) Incidents by hour of day (bar/histogram)
SELECT incident_hour, count(*) AS incidents
FROM cpd.daily_police_log
WHERE incident_hour IS NOT NULL
GROUP BY 1 ORDER BY 1;

-- 4) Historical: incidents per month (line)
SELECT date_trunc('month', incident_date)::date AS month, count(*) AS incidents
FROM cpd.daily_police_log
GROUP BY 1 ORDER BY 1;

-- 5) Busiest streets (bar)
SELECT street, count(*) AS incidents
FROM cpd.daily_police_log
WHERE street IS NOT NULL
GROUP BY 1 ORDER BY 2 DESC LIMIT 15;

-- 6) Day-of-week pattern (bar)
SELECT day_of_week, count(*) AS incidents
FROM cpd.daily_police_log
WHERE day_of_week IS NOT NULL
GROUP BY 1
ORDER BY array_position(ARRAY['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'], day_of_week);
