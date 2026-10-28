"""Line-delimited JSON protocol for the Tauri sidecar."""

import json


def decode_command(line):
    if len(line) > 65536:
        raise ValueError('Command too large')
    try:
        message = json.loads(line)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError('Invalid JSON') from exc
    if not isinstance(message, dict):
        raise ValueError('Command must be an object')
    ident, command, payload = message.get('id'), message.get('command'), message.get('payload')
    if type(ident) is not int or ident < 0 or not isinstance(command, str) or not command or not isinstance(payload, dict):
        raise ValueError('Invalid command envelope')
    return ident, command, payload


def encode_message(message):
    return json.dumps(message, separators=(',', ':'), allow_nan=False) + '\n'
