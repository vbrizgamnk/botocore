#!/usr/bin/env
# Copyright 2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.
import botocore.config
from tests import unittest
import mock

from botocore import args
from botocore.config import Config


class TestCreateClientArgs(unittest.TestCase):
    def setUp(self):
        self.args_create = args.ClientArgsCreator(None, None, None, None)

    def test_compute_s3_configuration(self):
        scoped_config = {}
        client_config = None
        self.assertIsNone(
            self.args_create.compute_s3_config(
                scoped_config, client_config))

    def test_compute_s3_config_only_scoped_config(self):
        scoped_config = {
            's3': {'use_accelerate_endpoint': True},
        }
        client_config = None
        self.assertEqual(
            self.args_create.compute_s3_config(scoped_config, client_config),
            {'use_accelerate_endpoint': True}
        )

    def test_client_s3_accelerate_from_varying_forms_of_true(self):
        scoped_config= {'s3': {'use_accelerate_endpoint': 'True'}}
        client_config = None

        self.assertEqual(
            self.args_create.compute_s3_config(
                {'s3': {'use_accelerate_endpoint': 'True'}},
                client_config=None),
            {'use_accelerate_endpoint': True}
        )
        self.assertEqual(
            self.args_create.compute_s3_config(
                {'s3': {'use_accelerate_endpoint': 'true'}},
                client_config=None),
            {'use_accelerate_endpoint': True}
        )
        self.assertEqual(
            self.args_create.compute_s3_config(
                {'s3': {'use_accelerate_endpoint': True}},
                client_config=None),
            {'use_accelerate_endpoint': True}
        )

    def test_client_s3_accelerate_from_client_config(self):
        self.assertEqual(
            self.args_create.compute_s3_config(
                scoped_config=None,
                client_config=Config(s3={'use_accelerate_endpoint': True})
            ),
            {'use_accelerate_endpoint': True}
        )

    def test_client_s3_accelerate_client_config_overrides_scoped(self):
        self.assertEqual(
            self.args_create.compute_s3_config(
                scoped_config={'s3': {'use_accelerate_endpoint': False}},
                client_config=Config(s3={'use_accelerate_endpoint': True})
            ),
            # client_config beats scoped_config
            {'use_accelerate_endpoint': True}
        )

    def test_client_s3_dualstack_handles_varying_forms_of_true(self):
        scoped_config= {'s3': {'use_dualstack_endpoint': 'True'}}
        client_config = None

        self.assertEqual(
            self.args_create.compute_s3_config(
                {'s3': {'use_dualstack_endpoint': 'True'}},
                client_config=None),
            {'use_dualstack_endpoint': True}
        )
        self.assertEqual(
            self.args_create.compute_s3_config(
                {'s3': {'use_dualstack_endpoint': 'true'}},
                client_config=None),
            {'use_dualstack_endpoint': True}
        )
        self.assertEqual(
            self.args_create.compute_s3_config(
                {'s3': {'use_dualstack_endpoint': True}},
                client_config=None),
            {'use_dualstack_endpoint': True}
        )
