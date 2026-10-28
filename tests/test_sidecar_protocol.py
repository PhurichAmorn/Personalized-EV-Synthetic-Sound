import unittest

from backend.protocol import decode_command, encode_message


class SidecarProtocolTest(unittest.TestCase):
    def test_decodes_correlated_command(self):
        self.assertEqual(decode_command(b'{"id":7,"command":"toggle","payload":{}}\n'),
                         (7, 'toggle', {}))

    def test_rejects_untrusted_inputs(self):
        for line in (b'not json', b'[]', b'{"id":true,"command":"toggle","payload":{}}',
                     b'{"id":1,"command":"toggle","payload":[]}',
                     b'{"id":1,"command":"toggle","payload":{}} trailing'):
            with self.subTest(line=line), self.assertRaises(ValueError):
                decode_command(line)

    def test_message_is_one_json_line(self):
        self.assertEqual(encode_message({'id': 7, 'result': {'ok': True}}),
                         '{"id":7,"result":{"ok":true}}\n')


if __name__ == '__main__':
    unittest.main()
