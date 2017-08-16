# Copyright 2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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
import threading
import os
import math
import time
import mock
import tempfile
import shutil
from datetime import datetime, timedelta

from botocore.vendored import requests
from dateutil.tz import tzlocal

from tests import unittest, IntegerRefresher, BaseEnvVar, random_chars
from botocore.credentials import EnvProvider, ContainerProvider
from botocore.credentials import InstanceMetadataProvider
from botocore.credentials import Credentials, ReadOnlyCredentials
from botocore.session import Session
from botocore.exceptions import InvalidConfigError


class TestCredentialRefreshRaces(unittest.TestCase):
    def assert_consistent_credentials_seen(self, creds, func):
        collected = []
        threads = []
        for _ in range(20):
            threads.append(threading.Thread(target=func, args=(collected,)))
        start = time.time()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        for creds in collected:
            # During testing, the refresher uses it's current
            # refresh count as the values for the access, secret, and
            # token value.  This means that at any given point in time,
            # the credentials should be something like:
            #
            # ReadOnlyCredentials('1', '1', '1')
            # ReadOnlyCredentials('2', '2', '2')
            # ...
            # ReadOnlyCredentials('30', '30', '30')
            #
            # This makes it really easy to verify we see a consistent
            # set of credentials from the same time period.  We just
            # check if all the credential values are the same.  If
            # we ever see something like:
            #
            # ReadOnlyCredentials('1', '2', '1')
            #
            # We fail.  This is because we're using the access_key
            # from the first refresh ('1'), the secret key from
            # the second refresh ('2'), and the token from the
            # first refresh ('1').
            self.assertTrue(creds[0] == creds[1] == creds[2], creds)

    def test_has_no_race_conditions(self):
        creds = IntegerRefresher(
            creds_last_for=2,
            advisory_refresh=1,
            mandatory_refresh=0
        )
        def _run_in_thread(collected):
            for _ in range(4000):
                frozen = creds.get_frozen_credentials()
                collected.append((frozen.access_key,
                                  frozen.secret_key,
                                  frozen.token))
        start = time.time()
        self.assert_consistent_credentials_seen(creds, _run_in_thread)
        end = time.time()
        # creds_last_for = 2 seconds (from above)
        # So, for example, if execution time took 6.1 seconds, then
        # we should see a maximum number of refreshes being (6 / 2.0) + 1 = 4
        max_calls_allowed = math.ceil((end - start) / 2.0) + 1
        self.assertTrue(creds.refresh_counter <= max_calls_allowed,
                        "Too many cred refreshes, max: %s, actual: %s, "
                        "time_delta: %.4f" % (max_calls_allowed,
                                              creds.refresh_counter,
                                              (end - start)))

    def test_no_race_for_immediate_advisory_expiration(self):
        creds = IntegerRefresher(
            creds_last_for=1,
            advisory_refresh=1,
            mandatory_refresh=0
        )
        def _run_in_thread(collected):
            for _ in range(100):
                frozen = creds.get_frozen_credentials()
                collected.append((frozen.access_key,
                                  frozen.secret_key,
                                  frozen.token))
        self.assert_consistent_credentials_seen(creds, _run_in_thread)


class TestAssumeRole(BaseEnvVar):
    def setUp(self):
        super(TestAssumeRole, self).setUp()
        self.make_request_patch = mock.patch(
            'botocore.endpoint.Endpoint.make_request')
        self.make_request = self.make_request_patch.start()
        self.http_response = requests.models.Response()
        self.http_response.status_code = 200
        self.tempdir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.tempdir, 'config')
        self.environ['AWS_CONFIG_FILE'] = self.config_file
        self.environ['AWS_ACCESS_KEY_ID'] = 'access_key'
        self.environ['AWS_SECRET_ACCESS_KEY'] = 'secret_key'

        self._provider_patches = []

        self.metadata_provider = self.patch_provider(InstanceMetadataProvider)
        self.env_provider = self.patch_provider(EnvProvider)
        self.container_provider = self.patch_provider(ContainerProvider)

    def patch_provider(self, provider_cls, path=None):
        if path is None:
            path = 'botocore.credentials.%s' % provider_cls.__name__
        mock_instance = mock.Mock(spec=provider_cls)
        mock_instance.load.return_value = None
        mock_instance.CANONICAL_NAME = provider_cls.CANONICAL_NAME
        mock_cls = mock.Mock(return_value=mock_instance)
        provider_patch = mock.patch(path, mock_cls)
        provider_patch.start()
        self._provider_patches.append(provider_patch)
        return mock_instance

    def tearDown(self):
        self.make_request_patch.stop()
        for provider_patch in self._provider_patches:
            provider_patch.stop()
        shutil.rmtree(self.tempdir)

    def create_assume_role_response(self, credentials, expiration=None):

        if expiration is None:
            expiration = self.some_future_time()

        response = {
            'Credentials': {
                'AccessKeyId': credentials.access_key,
                'SecretAccessKey': credentials.secret_key,
                'SessionToken': credentials.token,
                'Expiration': expiration
            },
            'AssumedRoleUser': {
                'AssumedRoleId': 'myroleid',
                'Arn': 'arn:aws:iam::1234567890:user/myuser'
            }
        }

        return self.http_response, response

    def create_random_credentials(self):
        return Credentials(
            'fake-%s' % random_chars(15),
            'fake-%s' % random_chars(35),
            'fake-%s' % random_chars(45)
        )

    def some_future_time(self):
        timeobj = datetime.now(tzlocal())
        return timeobj + timedelta(hours=24)

    def write_config(self, config):
        with open(self.config_file, 'w') as f:
            f.write(config)

    def assert_creds_equal(self, c1, c2):
        c1_frozen = c1
        if not isinstance(c1_frozen, ReadOnlyCredentials):
            c1_frozen = c1.get_frozen_credentials()
        c2_frozen = c2
        if not isinstance(c2_frozen, ReadOnlyCredentials):
            c2_frozen = c2.get_frozen_credentials()
        self.assertEqual(c1_frozen, c2_frozen)

    def test_assume_role(self):
        config = (
            '[profile A]\n'
            'role_arn = arn:aws:iam::123456789:role/RoleA\n'
            'source_profile = B\n\n'
            '[profile B]\n'
            'aws_access_key_id = abc123\n'
            'aws_secret_access_key = def456\n'
        )
        self.write_config(config)

        expected_creds = self.create_random_credentials()
        response = self.create_assume_role_response(expected_creds)
        self.make_request.return_value = response

        session = Session(profile='A')
        actual_creds = session.get_credentials()
        self.assert_creds_equal(actual_creds, expected_creds)
        self.assertEqual(self.make_request.call_count, 1)

    def test_environment_credential_source(self):
        config = (
            '[profile A]\n'
            'role_arn = arn:aws:iam::123456789:role/RoleA\n'
            'credential_source = Environment\n'
        )
        self.write_config(config)

        environment_creds = self.create_random_credentials()
        self.env_provider.load.return_value = environment_creds

        expected_creds = self.create_random_credentials()
        response = self.create_assume_role_response(expected_creds)
        self.make_request.return_value = response

        session = Session(profile='A')
        actual_creds = session.get_credentials()
        self.assert_creds_equal(actual_creds, expected_creds)

        self.assertEqual(self.make_request.call_count, 1)
        self.assertEqual(self.env_provider.load.call_count, 1)

    def test_instance_metadata_credential_source(self):
        config = (
            '[profile A]\n'
            'role_arn = arn:aws:iam::123456789:role/RoleA\n'
            'credential_source = Ec2InstanceMetadata\n'
        )
        self.write_config(config)

        metadata_creds = self.create_random_credentials()
        self.metadata_provider.load.return_value = metadata_creds

        expected_creds = self.create_random_credentials()
        response = self.create_assume_role_response(expected_creds)
        self.make_request.return_value = response

        session = Session(profile='A')
        actual_creds = session.get_credentials()
        self.assert_creds_equal(actual_creds, expected_creds)

        self.assertEqual(self.make_request.call_count, 1)
        self.assertEqual(self.metadata_provider.load.call_count, 1)

    def test_container_credential_source(self):
        config = (
            '[profile A]\n'
            'role_arn = arn:aws:iam::123456789:role/RoleA\n'
            'credential_source = EcsContainer\n'
        )
        self.write_config(config)

        container_creds = self.create_random_credentials()
        self.container_provider.load.return_value = container_creds

        expected_creds = self.create_random_credentials()
        response = self.create_assume_role_response(expected_creds)
        self.make_request.return_value = response

        session = Session(profile='A')
        actual_creds = session.get_credentials()
        self.assert_creds_equal(actual_creds, expected_creds)

        self.assertEqual(self.make_request.call_count, 1)
        self.assertEqual(self.container_provider.load.call_count, 1)

    def test_invalid_credential_source(self):
        config = (
            '[profile A]\n'
            'role_arn = arn:aws:iam::123456789:role/RoleA\n'
            'credential_source = CustomInvalidProvider\n'
        )
        self.write_config(config)

        with self.assertRaises(InvalidConfigError):
            Session(profile='A').get_credentials()

    def test_recursive_assume_role(self):
        config = (
            '[profile A]\n'
            'role_arn = arn:aws:iam::123456789:role/RoleA\n'
            'source_profile = B\n\n'
            '[profile B]\n'
            'role_arn = arn:aws:iam::123456789:role/RoleB\n'
            'source_profile = C\n\n'
            '[profile C]\n'
            'aws_access_key_id = abc123\n'
            'aws_secret_access_key = def456\n'
        )
        self.write_config(config)

        profile_b_creds = self.create_random_credentials()
        profile_b_response = self.create_assume_role_response(profile_b_creds)
        profile_a_creds = self.create_random_credentials()
        profile_a_response = self.create_assume_role_response(profile_a_creds)

        self.make_request.side_effect = [
            profile_b_response, profile_a_response]

        session = Session(profile='A')
        actual_creds = session.get_credentials()
        self.assert_creds_equal(actual_creds, profile_a_creds)

        self.assertEqual(self.make_request.call_count, 2)

    def test_recursive_assume_role_stops_at_static_creds(self):
        config = (
            '[profile A]\n'
            'role_arn = arn:aws:iam::123456789:role/RoleA\n'
            'source_profile = B\n\n'
            '[profile B]\n'
            'aws_access_key_id = abc123\n'
            'aws_secret_access_key = def456\n'
            'role_arn = arn:aws:iam::123456789:role/RoleB\n'
            'source_profile = C\n\n'
            '[profile C]\n'
            'aws_access_key_id = abc123\n'
            'aws_secret_access_key = def456\n'
        )
        self.write_config(config)

        profile_a_creds = self.create_random_credentials()
        profile_a_response = self.create_assume_role_response(profile_a_creds)

        self.make_request.side_effect = [profile_a_response]

        session = Session(profile='A')
        actual_creds = session.get_credentials()
        self.assert_creds_equal(actual_creds, profile_a_creds)

        self.assertEqual(self.make_request.call_count, 1)
