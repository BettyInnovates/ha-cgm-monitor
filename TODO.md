# TODO "move to more entities"

In the next step, we will move all attributes store in the main sensor entity to separate entities (with correct classes).

The main sensor should hold the glucose value from the original sensor.

There should be separate entities for:
- priority (critical,warning,normal)
- state (low,normal,high, etc.)
- trend (from original sensor, falling slightly, etc.)

The main sensor py and class should be refactored to reflect this in a very clean and readable way.

All templates in lovelace-templates need to be reworked for the new entities. Since there are a lot of workarounds in the templates,
to access attributes, those should be replaced with the easier way with the new entities.

Short documentation should be added to the README.md, containing all the new entities.

DONE