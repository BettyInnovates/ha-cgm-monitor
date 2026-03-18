# Current TODOs

The following table shows the bounds of thresholds for the state of the sensor. 

| bound input  | Values | State |
|--------------|--------|---|
| critical_low | < 40   | critical_low |
| very_low     | < 60   | very_low |
| low          | < 80   | warning |
| (target)     |        | ok |
| high         | > 140  | high |
| very_high    | > 180  | very_high |

TODO: Please implement the new thresholds in the `sensor.py` file. And adjust the documentation accordingly.

Exmaple yaml config:

```yaml
sensor:
  - platform: cgm_monitor
    name: "CGM Subject 1"
    glucose_sensor: "sensor.glucose_random_blood_sugar_01_value"
    trend_sensor: "sensor.glucose_random_trend_01_trend"
    critical_low_threshold: 40
    very_low_threshold: 60
    low_threshold: 80
    high_threshold: 140
    very_high_threshold: 180
    warning_low: 100
  - platform: cgm_monitor
    name: "CGM Subject 2"
    glucose_sensor: "sensor.glucose_random_sugar_02"
    trend_sensor: "sensor.glucose_random_trend_02"
```