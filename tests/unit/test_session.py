#!/usr/bin/env
# Copyright (c) 2012-2013 Mitch Garnaat http://garnaat.org/
# Copyright 2012-2013 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish, dis-
# tribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the fol-
# lowing conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABIL-
# ITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHOR BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#
import unittest
import os
import logging
import tempfile
import shutil

import mock

import botocore.session
import botocore.exceptions
from botocore.hooks import EventHooks


class BaseSessionTest(unittest.TestCase):

    def setUp(self):
        self.env_vars = {'profile': (None, 'FOO_PROFILE', None),
                         'region': ('foo_region', 'FOO_REGION', None),
                         'data_path': ('data_path', 'FOO_DATA_PATH', None),
                         'config_file': (None, 'FOO_CONFIG_FILE', None),
                         'access_key': ('foo_access_key', None, None),
                         'secret_key': ('foo_secret_key', None, None)}
        self.environ = {}
        self.environ_patch = mock.patch('os.environ', self.environ)
        self.environ_patch.start()
        self.environ['FOO_PROFILE'] = 'foo'
        self.environ['FOO_REGION'] = 'moon-west-1'
        data_path = os.path.join(os.path.dirname(__file__), 'data')
        self.environ['FOO_DATA_PATH'] = data_path
        config_path = os.path.join(os.path.dirname(__file__), 'cfg',
                                   'foo_config')
        self.environ['FOO_CONFIG_FILE'] = config_path
        self.session = botocore.session.get_session(self.env_vars)

    def tearDown(self):
        self.environ_patch.stop()


class SessionTest(BaseSessionTest):

    def setUp(self):
        super(SessionTest, self).setUp()
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        super(SessionTest, self).tearDown()
        shutil.rmtree(self.tempdir)

    def close_log_file_handler(self, filename):
        logger = logging.getLogger('botocore')
        handlers = logger.handlers
        for handler in handlers[:]:
            if hasattr(handler, 'stream') and handler.stream.name == filename:
                handler.stream.close()
                logger.removeHandler(handler)

    def test_profile(self):
        self.assertEqual(self.session.get_variable('profile'), 'foo')
        self.assertEqual(self.session.get_variable('region'), 'moon-west-1')
        self.session.get_variable('profile') == 'default'
        saved_region = self.environ['FOO_REGION']
        del self.environ['FOO_REGION']
        saved_profile = self.environ['FOO_PROFILE']
        del self.environ['FOO_PROFILE']
        session = botocore.session.get_session(self.env_vars)
        self.assertEqual(session.get_variable('profile'), None)
        self.assertEqual(session.get_variable('region'), 'us-west-1')
        self.environ['FOO_REGION'] = saved_region
        self.environ['FOO_PROFILE'] = saved_profile

    def test_file_logger(self):
        temp_file = os.path.join(self.tempdir, 'file_logger')
        self.session.set_file_logger(logging.DEBUG, temp_file)
        self.addCleanup(self.close_log_file_handler, temp_file)
        self.session.get_credentials()
        self.assertTrue(os.path.isfile(temp_file))
        with open(temp_file) as logfile:
            s = logfile.read()
        self.assertTrue('Found credentials' in s)

    def test_full_config_property(self):
        full_config = self.session.full_config
        self.assertTrue('profile "foo"' in full_config)
        self.assertTrue('default' in full_config)

    def test_register_unregister(self):
        calls = []
        handler = lambda **kwargs: calls.append(kwargs)
        self.session.register('service-created', handler)
        service = self.session.get_service('ec2')
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['service'], service)

        calls[:] = []
        self.session.unregister('service-created', handler)
        service = self.session.get_service('ec2')
        self.assertEqual(len(calls), 0)

    def test_emit_delegates_to_emitter(self):
        calls = []
        handler = lambda **kwargs: calls.append(kwargs)
        self.session.register('foo', handler)
        self.session.emit('foo')
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['event_name'], 'foo')

    def test_emitter_can_be_passed_in(self):
        events = EventHooks()
        session = botocore.session.Session(self.env_vars, events)
        calls = []
        handler = lambda **kwargs: calls.append(kwargs)
        events.register('foo', handler)

        session.emit('foo')
        self.assertEqual(len(calls), 1)

    def test_available_events(self):
        self.assertTrue('after-call' in botocore.session.AllEvents)
        self.assertTrue('after-parsed' in botocore.session.AllEvents)
        self.assertTrue('before-call' in botocore.session.AllEvents)
        self.assertTrue('service-created' in botocore.session.AllEvents)

    def test_create_events(self):
        event = self.session.create_event('before-call', 'foo', 'bar')
        self.assertEqual(event, 'before-call.foo.bar')
        event = self.session.create_event('after-call', 'foo', 'bar')
        self.assertEqual(event, 'after-call.foo.bar')
        event = self.session.create_event('after-parsed', 'foo',
                                          'bar', 'fie', 'baz')
        self.assertEqual(event, 'after-parsed.foo.bar.fie.baz')
        event = self.session.create_event('service-created')
        self.assertEqual(event, 'service-created')
        self.assertRaises(botocore.exceptions.EventNotFound,
                          self.session.create_event, 'foo-bar')


class TestBuiltinEventHandlers(BaseSessionTest):
    def setUp(self):
        super(TestBuiltinEventHandlers, self).setUp()
        self.builtin_handlers = [
            ('foo', self.on_foo),
        ]
        self.foo_called = False
        self.handler_patch = mock.patch('botocore.handlers.BUILTIN_HANDLERS',
                                        self.builtin_handlers)
        self.handler_patch.start()

    def on_foo(self, **kwargs):
        self.foo_called = True

    def tearDown(self):
        super(TestBuiltinEventHandlers, self).setUp()
        self.handler_patch.stop()

    def test_registered_builtin_handlers(self):
        session = botocore.session.Session(self.env_vars, None,
                                           include_builtin_handlers=True)
        session.emit('foo')
        self.assertTrue(self.foo_called)


if __name__ == "__main__":
    unittest.main()
