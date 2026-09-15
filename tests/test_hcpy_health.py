"""No real broker/appliance traffic; exercise native callbacks and stall isolation."""
import json
from threading import Event
from unittest.mock import Mock

import pytest
import paho.mqtt.client as mqtt

import hc2mqtt
import hcpy_health
from hcpy_health import Health, check
from HCSocket import HCSocket


def test_independent_stalls_idle_outage_recovery(tmp_path, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(hcpy_health.time, 'monotonic', lambda: now[0])
    path = tmp_path / 'health'
    health = Health(1, path)
    assert check(path, 'live') and not check(path, 'ready')
    health.progress('mqtt', True)
    health.progress('device-0', True)
    assert check(path, 'ready')
    # Actual protocol callbacks keep idle-but-responsive loops fresh.
    now[0] = 350
    health.mqtt_log(None, None, None, 'Received PINGRESP')
    health.progress('device-0')
    assert check(path, 'ready')
    health.progress('device-0', False)
    assert check(path, 'live') and not check(path, 'ready')
    health.progress('device-0', True)
    # A healthy MQTT loop must not mask a stalled appliance loop.
    now[0] = 651
    health.progress('mqtt')
    assert not check(path, 'live')
    health.progress('device-0')
    assert check(path, 'ready')
    now[0] = 952
    health.progress('device-0')
    assert not check(path, 'live')  # nor the reverse
    Health(1, path)
    assert not check(path, 'ready')  # restart never inherits readiness


def test_real_paho_ping_response_callback_without_socket(tmp_path):
    health = Health(1, tmp_path / 'health')
    client = mqtt.Client('synthetic')
    client.on_log = health.mqtt_log
    calls = []
    health.progress = lambda *args: calls.append(args)
    # Pinned native parser emits this public on_log event only after PINGRESP.
    client._in_packet['remaining_length'] = 0
    assert client._handle_pingresp() == mqtt.MQTT_ERR_SUCCESS
    assert calls == [('mqtt',)]
    health.mqtt_log(None, None, None, 'unrelated synthetic log')
    assert calls == [('mqtt',)]


def test_native_websocket_pong_callback_only_after_receive(monkeypatch):
    socket_module = __import__('HCSocket')
    sock = Mock(spec=HCSocket)
    sock.host, sock.port, sock.uri, sock.http = 'synthetic.invalid', 80, 'ws://synthetic.invalid', True
    progress = []
    sock.on_progress = lambda: progress.append('pong')
    monkeypatch.setattr(socket_module.socket, 'create_connection', lambda *a, **kw: Mock())
    received = {}
    def app(*args, **kwargs):
        received.update(kwargs)
        return Mock()
    monkeypatch.setattr(socket_module.websocket, 'WebSocketApp', app)
    HCSocket.run_forever(sock, Mock(), Mock(), Mock(), Mock())
    assert progress == []
    received['on_pong'](None, b'')
    assert progress == ['pong']


def test_appliance_handshake_idle_and_disconnect(tmp_path, monkeypatch):
    health = Health(1, tmp_path / 'health')
    health.progress('mqtt', True)
    shutdown = Event()
    socket = Mock()
    device = Mock()
    device.state = {}
    monkeypatch.setattr(hc2mqtt, 'HCSocket', lambda *a: socket)
    monkeypatch.setattr(hc2mqtt, 'HCDevice', lambda *a: device)
    monkeypatch.setattr(hc2mqtt, 'handle_device_message', lambda *a: None)
    states = []
    def run_forever(on_message, on_open, on_close):
        on_open(None)
        states.append(check(health.path, 'ready'))
        on_message({'synthetic': 'state'})
        states.append(check(health.path, 'ready'))
        socket.on_progress()
        states.append(check(health.path, 'ready'))
        on_close(None, 0, '')
        states.append(check(health.path, 'ready'))
        shutdown.set()
    device.run_forever = run_forever
    hc2mqtt.client_connect(Mock(), {'host': 'synthetic.invalid', 'name': 'synthetic', 'key': 'synthetic'},
                          'synthetic', '', False, shutdown=shutdown, health=health, health_component='device-0')
    assert states == [False, True, True, False]
    assert check(health.path, 'live')
    assert set(json.loads(health.path.read_text())['components']) == {'mqtt', 'device-0'}


@pytest.mark.parametrize('data', ['{', '{}', '{"version":1,"components":{}}'])
def test_missing_and_invalid_fail_closed(tmp_path, data):
    path = tmp_path / 'health'
    assert not check(path, 'live')
    path.write_text(data)
    assert not check(path, 'live')
