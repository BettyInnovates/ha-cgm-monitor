# TODO priority mapping

There should be a new attribute being calculated from the state and the trend of the entity and saved to the entity.

A default priority mapping should be read from default-priority-mapping.yaml, and overrides can be configured in the 
platform configuration. Priorities are "critical", "warning" and "normal". Mappings not defined in the configuration
will be mapped to "normal".

Example:

```yaml
sensor:
  - platform: cgm_monitor
    name: "CGM Subject 1"
    glucose_sensor: "sensor.glucose_random_sugar_01"
    trend_sensor: "sensor.glucose_random_trend_01"
    priority_mapping_overrides:
      - state: "critical_low"
        trend: "falling"
        priority: "critical"
```

Also, unavailable state from the source sensor should lead to a priority of "critical".