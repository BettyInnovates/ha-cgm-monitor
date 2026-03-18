# CGM Monitor


## Sensor States

The sensor state reflects the current glucose level relative to the configured thresholds:

| State | Condition |
|---|---|
| `critical_low` | glucose < `critical_low_threshold` (default 40) |
| `very_low` | glucose < `very_low_threshold` (default 60) |
| `warning` | glucose < `low_threshold` (default 80) |
| `ok` | glucose within target range |
| `high` | glucose > `high_threshold` (default 140) |
| `very_high` | glucose > `very_high_threshold` (default 180) |


## Config

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
  - platform: cgm_monitor
    name: "CGM Subject 2"
    glucose_sensor: "sensor.glucose_random_sugar_02"
    trend_sensor: "sensor.glucose_random_trend_02"
```