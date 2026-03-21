# TODO Feature "Subject Events"

- It should be possible to manually and automatically save events per subject.
- There should be a form on the subject detail page to add and delete events.

Requirements:
  - Events should hold metadata that can be used later on for reporting and summaries (even calculated: like average, sum/day of an attribute)
  - Events should be visible in apexcharts and other ha charts.
  - Adding/Deleting events should be a service call, so it can be used in other places like automations.

Ideas:
  - I would prefer a calendar or similar feature/data structure be used to save those events, to make use of the existing calendar features.