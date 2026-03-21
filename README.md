# CGM Monitor

## Configuration

Each entry in `configuration.yaml` creates the following entities (using "CGM Subject 1" as an example, slug `cgm_subject_1`):

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
    priority_mapping_overrides:
      - state: "low"
        trend: "steady"
        priority: "critical"
      - state: "high"
        trend: "rising_quickly"
        priority: "warning"
```

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

## Priority

The priority entity value is derived from the combination of the current CGM state and trend.

The default mapping is defined in `custom_components/cgm_monitor/default-priority-mapping.yaml`. Any combination not listed there defaults to `normal`. If the glucose source sensor is unavailable, priority is always `critical`.

Per-sensor overrides can be added in `configuration.yaml`. An override replaces a default entry for the given `(state, trend)` pair, or adds a new one if it wasn't in the defaults:

Changes to `default-priority-mapping.yaml` take effect after triggering the CGM Monitor reload service — no HA core restart needed.

## Notifications

Notifications are driven by HA automations, giving you full control over when and how you are notified. Enable or disable notifications per subject by enabling/disabling the corresponding automation.

A template automation is provided in `templates/automation/notification-automation.yaml`. Import it, adjust the subject name and notify target, and you're done.

### Example automation

```yaml
alias: CGM Subject 1 Notifications
description: >
  Send push notifications when the CGM priority changes to warning or critical.
  Disable this automation to suppress notifications for this subject.
  Configure the notify target(s) in the action section below.
triggers:
  - trigger: state
    entity_id: sensor.cgm_subject_1_priority
    to:
      - warning
      - critical
conditions:
  - condition: template
    value_template: >
      {{ trigger.from_state.state != trigger.to_state.state }}
actions:
  - choose:
      - conditions:
          - condition: template
            value_template: "{{ trigger.to_state.state == 'critical' }}"
        sequence:
          - action: notify.mobile_app_myphone
            data:
              title: CGM Critical
              message: >
                CGM Subject 1: {{ states('sensor.cgm_subject_1') }} mg/dL,
                State: {{ states('sensor.cgm_subject_1_state') }},
                Trend: {{ states('sensor.cgm_subject_1_trend') }}
              data:
                ttl: 0
                priority: high
                channel: alarm_stream
      - conditions:
          - condition: template
            value_template: "{{ trigger.to_state.state == 'warning' }}"
        sequence:
          - action: notify.mobile_app_myphone
            data:
              title: CGM Warning
              message: >
                CGM Subject 1: {{ states('sensor.cgm_subject_1') }} mg/dL,
                State: {{ states('sensor.cgm_subject_1_state') }},
                Trend: {{ states('sensor.cgm_subject_1_trend') }}
  - action: persistent_notification.create
    data:
      title: >
        {{ 'CGM Warning' if trigger.to_state.state == 'warning' else 'CGM Critical' }}
      message: >
        CGM Subject 1: {{ states('sensor.cgm_subject_1') }} mg/dL,
        State: {{ states('sensor.cgm_subject_1_state') }},
        Trend: {{ states('sensor.cgm_subject_1_trend') }}
      notification_id: cgm_subject_1_notification
mode: single
```

## Subject Events

Each subject gets a calendar entity and a set of helper entities for logging events (insulin doses, meals, etc.) directly from the dashboard.

| Entity ID | Domain | Description |
|---|---|---|
| `calendar.cgm_subject_1_events` | `calendar` | Event calendar, visible in the HA calendar card and UI. |
| `select.cgm_subject_1_event_type` | `select` | Event type picker: `Insulin`, `Meal`, `Custom`. |
| `select.cgm_subject_1_event_unit` | `select` | Dose unit picker: `IU`, `BE`. |
| `number.cgm_subject_1_event_dose` | `number` | Dose amount (0–100, step 0.5). |
| `text.cgm_subject_1_event_note` | `text` | Free-text note. |
| `date.cgm_subject_1_event_date` | `date` | Event date (defaults to today). |
| `time.cgm_subject_1_event_time` | `time` | Event time (defaults to 12:00). |

### Services

**`cgm_monitor.add_event`** — Add an event to a subject's calendar.

| Field | Required | Description |
|---|---|---|
| `subject` | yes | Subject name, e.g. `CGM Subject 1` |
| `type` | yes | `Insulin`, `Meal`, or `Custom` |
| `date` | no | Date in `YYYY-MM-DD` format. Defaults to today. |
| `time` | no | Time in `HH:MM` format. Defaults to `12:00`. |
| `unit` | no | `IU` or `BE` |
| `dose` | no | Numeric dose amount |
| `note` | no | Free-text note |

**`cgm_monitor.delete_event`** — Remove an event by its UID.

| Field | Required | Description |
|---|---|---|
| `subject` | yes | Subject name |
| `uid` | yes | Event UID (shown in the calendar event details) |

## HACS addons

For better UI:
- https://github.com/benct/lovelace-multiple-entity-row (Multiple entity row attributes etc.)
- https://github.com/RomRider/apexcharts-card (Better charts)
- https://github.com/Nerwyn/custom-card-features (Actions card features)
- https://github.com/ofekashery/vertical-stack-in-card (Vertical stack card)
- https://github.com/thomasloven/hass-browser_mod (reload page)