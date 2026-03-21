# TODO Refactoring "Notification Automations"

To make more use of declarative configuration and flexibility the notification notifications should be refactored.

- ha automations should be used for the notification automation (will be configured manually, template in templates/)
- the entity for disabling notifications per subject should be removed (will be covered by enabling/disabling the automation)
- there should be a service to trigger the notifications via ha automation for a specific subject
- targets for the notifications should be configured in the automation (removed from configuration, hint: fix documentation)

- clean leftovers in code