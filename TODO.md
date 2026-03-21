# TODO Feature "Export Reporting"

## Exporting

There should be a service that exports certain data to files. That service can be triggered with a date as a parameter.

For all cgm subjects, all relevant events (glucose, trend, state, priority) should be exported to a csv file with 
the subject name (whitespaces replaced) and date as filename (e.g., CGM_Subject_1_2018-01-01.csv).

Columns should be:
 - timestamp
 - glucose
 - trend
 - state
 - priority
 - thresholds (high, low, etc.)
 - etc.

Timestamp will be derived from the glucose events and all others read at that time.

Also, all calendar events should be exported to CGM_Subject_1_2018-01-01_events.csv.

If the file exists, it should be replaced.

## Statistics and Analysis

Another service should aggregate the data and provide statistics. It should generate a CSV file with both the first and 
second events aggregated. CGM_Subject_1_2026-01-01_full.csv. Also, the service generates a graph with matplotlib 
containing:
  - glucose values
  - thresholds drawn as background orientation
  - dots or event icons for calendar events (insulin, meal, etc.)

A PDF file should be generated with the graphs from all subjects.

## Reporting

A service should be available to send all the files generated before as email to a list of targets. The ha smtp platform 
should be used.

The service should have two parameters:
  - id of the configured smtp platform entry (from configuration.json)
  - list of targets (comma separated)
  - day
