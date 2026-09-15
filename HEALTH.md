# Fleet hcpy progress probes — prepared source only

Owner/source: upstream `hcpy2-0/hcpy`, pinned `0f2136d39c15864e5a03a1ad5ade326525102313`.
The existing build checkout is `work/CODEX/hcpy-upstream-build`; this patch lives in
its separate Git worktree `work/CODEX/hcpy-worker-health`. The build checkout's
uncommitted Dockerfile hardening overlay is preserved. No appliance commands,
broker messages, rebuild, deployment or restart were performed for this change.

## Contract

`/usr/local/bin/python /app/hcpy_health.py live /tmp/hcpy-health.json`

Use `ready` for readiness. Receipts need container-local writable `/tmp`, never a
persistent/shared volume. They contain only fixed `mqtt`/`device-N` IDs, monotonic
progress/deadline/last-success times, and readiness flags. No hostnames, appliance
names, MQTT topics, messages or keys are retained. Missing/malformed state fails
closed; process initialization replaces any previous receipt and starts unready.

Every configured appliance and the MQTT receive loop has its **own 300-second
progress budget**. Progress from one cannot hide a stalled sibling. Startup can
use `live`; readiness requires MQTT CONNACK success and at least one parsed device
state update after each appliance connection. Disconnections/failed connection
attempts remain live but unready while native reconnection continues.

- MQTT: actual connect, disconnect, failed-reconnect and completed control callback
  events; idle receive progress uses the exact public `on_log` event `Received
  PINGRESP` emitted by the pinned Paho parser. Other log strings are ignored.
- Appliance: completed parsed message callback, disconnect/reconnect outcomes,
  and native WebSocket `on_pong` receipt. A WebSocket open alone is not readiness.
- No timer updates health; no replacement of either library's network loop,
  extra broker publication, appliance request, PID check, or socket-open probe.
- MQTT `on_publish` is deliberately not used for receive-loop liveness: QoS0
  publication can finish on an appliance thread while the MQTT receive loop is
  stalled. Existing publish/command semantics remain unchanged.

The budget covers MQTT keepalive70/reconnect delays (up to120), and the appliance
120-second ping interval/10-second timeout plus handshake/reconnect. Observe the
real new image before enabling liveness; acceptance still needs idle protocol
receipt, disconnected dependency, and subsequent recovery observations. Readiness
is transport/parser responsiveness, **not proof of every subscription's SUBACK or
end-to-end delivery to Home Assistant**. Existing QoS0 publishes have no broker
acknowledgment. No successful delivery claim is inferred from health.

## Dependencies and build ownership

Scoped live package metadata verified Paho MQTT **1.6.1** and websocket-client
**1.9.2**. The exact PINGRESP log contract must be checked when upgrading Paho.
Tests drive its real packet handler without any socket and drive the actual
WebSocket callback construction against a synthetic transport.

`Dockerfile.health` layers only changed Python sources on deployed hcpy digest
`673f857327eed66ea9da6e360eccfaa03e3ab6881f6615ed2d64070c76b7d6a2`, preserving
existing dependencies and the operator's runtime build overlay. It does not use
the upstream Dockerfile that lacks those local build changes. A release owner
must build/pin this source, wire probes, and validate runtime before APP-07 closes.
This branch is not pushed to upstream or Forge, and no new clone was created.

## Validation

`python -m pytest -q tests`

84 tests pass with synthetic data, including per-loop stall isolation, idle
PINGRESP/pong callbacks, stale and malformed receipts, startup, appliance
handshake/disconnect, and existing command/discovery/device parsing behavior.
Local test interpreter is Python3.14; deployed image uses the verified Python3.13.15
runtime and still needs image acceptance.

Upstream references checked:

- [Paho1.6.1 source: public callbacks and PINGRESP receive event](https://github.com/eclipse-paho/paho.mqtt.python/blob/v1.6.1/src/paho/mqtt/client.py)
- [websocket-client WebSocketApp callbacks](https://websocket-client.readthedocs.io/en/latest/app.html)
