# TODO Feature Notifications

The cgm monitor should send notifications to companion apps depending on the priority state.

In the configuration there should be a list of devices that should be notified, per subject.

```yaml
sensor:
  - platform: cgm_monitor
    name: "CGM Subject 1"
    glucose_sensor: "sensor.glucose_random_blood_sugar_01_value"
    trend_sensor: "sensor.glucose_random_trend_01_trend"
    # ...
    notify:
      - device_tracker.mobile1
      - device_tracker.mobile2
```

- Notifications should only be sent to the device tracker of the device.
- There should be a binary sensor for each subject to enable or disable notifications.
- Alarm priority should be, depending on the priority state:
    - warning: notification (push notification)
    - critical: critical (push notification + android alarm)

Notification:
- Title: "CGM Warning"
- Message: "Subject 1: 123 mg/dL, State: High, Trend: High, Priority: Warning"

- After executing the notification event, there should be an attribute added to the priority state, to keep track if the notification has been sent already.
- Also if the attribute is set, the notification should not be sent again.