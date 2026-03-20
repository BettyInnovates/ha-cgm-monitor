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

## Entities

Each entry in `configuration.yaml` creates the following entities (using "CGM Subject 1" as an example, slug `cgm_subject_1`):

| Entity ID | Domain | Description |
|---|---|---|
| `sensor.cgm_subject_1` | `sensor` | Current glucose reading (mg/dL). Becomes unavailable when the source sensor is unavailable or unknown. |
| `sensor.cgm_subject_1_state` | `sensor` | CGM state category: `critical_low`, `very_low`, `low`, `ok`, `high`, `very_high`. Becomes unavailable when glucose is unavailable. |
| `sensor.cgm_subject_1_priority` | `sensor` | Alert priority: `critical`, `warning`, or `normal`. Always `critical` when glucose is unavailable. |
| `sensor.cgm_subject_1_trend` | `sensor` | Trend string mirrored from the configured trend source sensor. Only created when `trend_sensor` is configured. |
| `number.cgm_subject_1_critical_low_threshold` | `number` | Adjustable threshold (mg/dL). Value persists across restarts. |
| `number.cgm_subject_1_very_low_threshold` | `number` | |
| `number.cgm_subject_1_low_threshold` | `number` | |
| `number.cgm_subject_1_high_threshold` | `number` | |
| `number.cgm_subject_1_very_high_threshold` | `number` | |

---

## Sensor States

The state entity reflects the current glucose level relative to the configured thresholds:

| State | Condition |
|---|---|
| `critical_low` | glucose < `critical_low_threshold` (default 40) |
| `very_low` | glucose < `very_low_threshold` (default 60) |
| `low` | glucose < `low_threshold` (default 80) |
| `ok` | glucose within target range |
| `high` | glucose > `high_threshold` (default 140) |
| `very_high` | glucose > `very_high_threshold` (default 180) |

---

## Priority

The priority entity value is derived from the combination of the current CGM state and trend.

The default mapping is defined in `custom_components/cgm_monitor/default-priority-mapping.yaml`. Any combination not listed there defaults to `normal`. If the glucose source sensor is unavailable, priority is always `critical`.

Per-sensor overrides can be added in `configuration.yaml`. An override replaces a default entry for the given `(state, trend)` pair, or adds a new one if it wasn't in the defaults:

```yaml
sensor:
  - platform: cgm_monitor
    name: "CGM Subject 1"
    glucose_sensor: "sensor.glucose_random_blood_sugar_01_value"
    trend_sensor: "sensor.glucose_random_trend_01_trend"
    priority_mapping_overrides:
      - state: "low"
        trend: "steady"
        priority: "critical"
      - state: "high"
        trend: "rising_quickly"
        priority: "warning"
```

Changes to `default-priority-mapping.yaml` take effect after triggering the CGM Monitor reload service — no HA core restart needed.

---

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
