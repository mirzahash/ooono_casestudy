"""Check that encrypted-key authentication uses the connector's supported option."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import snowflake_io


class SnowflakeAuthTests(unittest.TestCase):
    def test_passphrase_reaches_the_supported_connector_option(self):
        config = {'authenticator': 'SNOWFLAKE_JWT', 'private_key_file': 'test-key.p8'}
        with patch.dict(os.environ, {'SNOWFLAKE_PRIVATE_KEY_PASSWORD': 'test-only'}), \
             patch('snowflake.connector.connect') as connect:
            snowflake_io.connect(config)
        options = connect.call_args.kwargs
        self.assertEqual(options['private_key_file_pwd'], 'test-only')
        self.assertNotIn('private_key_password', options)
        self.assertNotIn('private_key_file_pwd', config)
