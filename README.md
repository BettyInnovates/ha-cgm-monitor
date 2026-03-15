# CGM Monitor


## Config

```yaml
sensor:
  - platform: cgm_monitor
    name: "CGM Subject 1"
    glucose_sensor: "sensor.glucose_random_sugar_01"
    trend_sensor: "sensor.glucose_random_trend_01"
    warning_high: 200
    warning_low: 100
  - platform: cgm_monitor
    name: "CGM Subject 2"
    glucose_sensor: "sensor.glucose_random_sugar_02"
    trend_sensor: "sensor.glucose_random_trend_02"
```