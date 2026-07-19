# Multi-Robot Session Switcher

Switch between robot sessions without restarting.

## Config

```json
{
  "sessions": [
    {"id": "alpha", "endpoint": "ws://192.168.1.10:9090"},
    {"id": "beta", "endpoint": "ws://192.168.1.11:9090"}
  ],
  "active": "alpha"
}
```

## Commands

```
lappa session list
lappa session switch beta
lappa session status
```

Switching saves the current session state and restores the target.
