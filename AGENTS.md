# CGM Monitor — Agent Notes

## What this is
A Home Assistant custom component that wraps existing CGM (Continuous Glucose Monitor) sensor entities and monitors glucose values against configurable warning thresholds. Based on the HA core `plant` component pattern.

## Current state
- Working sensor platform at `custom_components/cgm_monitor/`
- Config via YAML (`sensor: - platform: cgm_monitor`)
- Tracks `glucose_sensor` (required) and `trend_sensor` (optional)
- State is `ok` or `problem`; problem triggers when glucose is outside `warning_low`/`warning_high`

## Key hints
- **Domain/folder name is `cgm_monitor`** — the old `custom_components/ha-cgm-monitor/` folder is a leftover from the plant copy and should be deleted
- **No config flow** — setup is YAML-only; no UI onboarding yet
- **Trend sensor is passive** — its value is exposed as an attribute but not checked against any threshold
- **No history loading** — unlike the plant component, there is no recorder/history initialization on startup
- **Deploy**: `deploy.sh` mounts the HA config share and copies the component folder; update the mount path if the share address changes

## Coding Guidelines
- Clean, simple and readable code
- Always prefer home assistant's framework over custom code, datastore, etc.
- Use classes and methods where appropriate and split into multiple files where appropriate. Keep it simple and methods 
  only as long as they are not too complex.