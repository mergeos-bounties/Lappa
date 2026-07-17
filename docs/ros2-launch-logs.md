# ROS2 launch log streaming

Lappa streams Docker ROS2 launch output and native preview lifecycle messages into
**ROS2 / Docker → Launch Logs**. The panel polls once per second and requests only
events newer than its last cursor, so long-running launches do not repaint or
duplicate their full history.

## Safety and sources

- `docker` events come from `/tmp/lappa_ros2_launch.log` through the bounded
  `/ros2_ws.sh logs` helper.
- `native` events record local preview start/stop activity in the same panel.
- Passwords, tokens, API keys, Authorization values, Bearer credentials, URL
  credentials, GitHub tokens, and AWS access-key IDs are replaced with
  `[REDACTED]` before an event enters the shared buffer.
- The in-memory buffer retains at most 2,000 events. API responses are capped at
  500 events per request.

Automation clients can use the same stream:

```text
GET /api/docker/launch/logs?after=0&limit=200
```

Use the returned `cursor` as the next `after` value. The CLI equivalent is:

```text
lappa docker logs --after 0 --limit 200
```

## Evidence checklist

- [x] Dedicated Launch Logs tab in the ROS2 / Docker IDE panel.
- [x] Incremental Docker/native messages with source and stream labels.
- [x] Secret values displayed as `[REDACTED]`.
- [x] Cursor and overlapping-tail regression tests.
- [x] Screenshot: [ROS2 launch log panel](https://github.com/user-attachments/assets/e87d96dc-4ca7-4020-895e-34988b3e9aa4).
