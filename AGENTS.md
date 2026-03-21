# CGM Monitor — Agent Notes

## What this is
A Home Assistant custom component that wraps existing CGM (Continuous Glucose Monitor) sensor entities and monitors 
glucose values against configurable warning thresholds.

## Current state
- Working sensor platform at `custom_components/cgm_monitor/`
- Config via YAML (`sensor: - platform: cgm_monitor`)

## Key hints
- **No config flow** — setup is YAML-only
- **Deploy**: `deploy.sh` mounts the HA config share and copies the component folder; update the mount path if the share address changes

## Coding Guidelines
- Clean, simple and readable code
- Always prefer home assistant's framework over custom code, datastore, etc.
- Use classes and methods where appropriate and split into multiple files where appropriate. Keep it simple and methods 
  only as long as they are not too complex.
- Please adjust the README.md file to reflect any changes.