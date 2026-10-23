# Architecture

```text
Restaurant camera
      |
      v
Edge OpenCV worker -- anonymous occupancy events --> FastAPI
                                                   |      |
                                                   v      v
                                             State engine SQLite
                                                   |
                                                   v
                                           React operations UI
```

The edge worker converts local frames into table-zone occupancy observations. Frames, faces, and person identifiers do not cross the edge boundary. The backend applies explicit state transitions and timer rules, persists operational events, and exposes alerts to the dashboard.

## Table state machine

```text
AVAILABLE_CLEAN -> OCCUPIED -> ATTENTION_DUE
                         |
                         v
             VACATED_NEEDS_CLEANING -> CLEANING -> AVAILABLE_CLEAN
```

Every automated transition records its source, timestamp, evidence, and resulting state. Staff actions are separate events.

