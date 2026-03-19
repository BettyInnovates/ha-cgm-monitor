# CGM Monitor

## used HACS addons

For better UI:
- https://github.com/benct/lovelace-multiple-entity-row (Multiple entity row attributes etc.)
- https://github.com/RomRider/apexcharts-card (Better charts)
- https://github.com/Nerwyn/custom-card-features (Actions card features)
- https://github.com/ofekashery/vertical-stack-in-card (Vertical stack card)

## CGM Subject Card (debug)

A Lovelace card showing all readings, thresholds, and attributes for a single subject.

**1. Register the resource** in `configuration.yaml` (or via Settings → Dashboards → Resources):

```yaml
lovelace:
  resources:
    - url: /local/cgm-subject-card.js
      type: module
```

Copy `www/cgm-subject-card.js` from this repo into your HA `config/www/` directory.

**2. Add to a dashboard:**

```yaml
type: custom:cgm-subject-card
sensor: sensor.cgm_subject_1
```

The card automatically reads the matching `number.*` threshold entities and re-renders whenever any value changes.

---

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
  - platform: cgm_monitor
    name: "CGM Subject 2"
    glucose_sensor: "sensor.glucose_random_sugar_02"
    trend_sensor: "sensor.glucose_random_trend_02"
```