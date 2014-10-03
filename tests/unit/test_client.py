#!/usr/bin/env
# Copyright 2014 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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
from tests import unittest
import mock

from botocore import model
from botocore import client
from botocore.client import ParamValidationError
from botocore import exceptions


class TestAutoGeneratedClient(unittest.TestCase):
    def setUp(self):
        self.service_description = {
            'metadata': {
                'apiVersion': '2014-01-01',
                'endpointPrefix': 'myservice',
                'signatureVersion': 'v4',
                'protocol': 'query'
            },
            'operations': {
                'TestOperation': {
                    'name': 'TestOperation',
                    'http': {
                        'method': 'POST',
                        'requestUri': '/',
                    },
                    'input': {'shape': 'TestOperationRequest'},
                }
            },
            'shapes': {
                'TestOperationRequest': {
                    'type': 'structure',
                    'required': ['Foo'],
                    'members': {
                        'Foo': {'shape': 'StringType'},
                        'Bar': {'shape': 'StringType'},
                    }
                },
                'StringType': {'type': 'string'}
            }
        }
        self.loader = mock.Mock()
        self.loader.load_service_model.return_value = self.service_description

    def test_client_generated_from_model(self):
        # Verify we can go from JSON model -> autogenerated client.
        endpoint_creator = mock.Mock()
        creator = client.ClientCreator(self.loader, endpoint_creator)
        service_client = creator.create_client('myservice', 'us-west-2')
        self.assertTrue(hasattr(service_client, 'test_operation'))

    def test_client_makes_call(self):
        endpoint_creator = mock.Mock()
        endpoint = mock.Mock()
        endpoint_creator.create_endpoint.return_value = endpoint
        endpoint.make_request.return_value = (mock.Mock(status_code=200), {})
        creator = client.ClientCreator(self.loader, endpoint_creator)

        service_client = creator.create_client('myservice', 'us-west-2')
        response = service_client.test_operation(Foo='one', Bar='two')
        self.assertEqual(response, {})

    def test_client_makes_call_with_error(self):
        endpoint_creator = mock.Mock()
        endpoint = mock.Mock()
        endpoint_creator.create_endpoint.return_value = endpoint
        error_response = {
            'Error': {'Code': 'code', 'Message': 'error occurred'}
        }
        endpoint.make_request.return_value = (mock.Mock(status_code=400),
                                              error_response)
        creator = client.ClientCreator(self.loader, endpoint_creator)

        service_client = creator.create_client('myservice', 'us-west-2')
        with self.assertRaises(client.ClientError):
            service_client.test_operation(Foo='one', Bar='two')

    def test_client_validates_params(self):
        endpoint_creator = mock.Mock()
        creator = client.ClientCreator(self.loader, endpoint_creator)

        service_client = creator.create_client('myservice', 'us-west-2')
        with self.assertRaises(ParamValidationError):
            # Missing required 'Foo' param.
            service_client.test_operation(Bar='two')

    def test_client_with_custom_params(self):
        endpoint_creator = mock.Mock()
        creator = client.ClientCreator(self.loader, endpoint_creator)

        service_client = creator.create_client('myservice', 'us-west-2',
                                               is_secure=False, verify=False)
        endpoint_creator.create_endpoint.assert_called_with(
            mock.ANY, 'us-west-2', is_secure=False,
            endpoint_url=None, verify=False)

    def test_client_with_endpoint_url(self):
        endpoint_creator = mock.Mock()
        creator = client.ClientCreator(self.loader, endpoint_creator)

        service_client = creator.create_client('myservice', 'us-west-2',
                                               endpoint_url='http://custom.foo')
        endpoint_creator.create_endpoint.assert_called_with(
            mock.ANY, 'us-west-2', is_secure=True,
            endpoint_url='http://custom.foo', verify=None)

    def test_operation_cannot_paginate(self):
        endpoint_creator = mock.Mock()
        pagination_config = {
            'pagination': {
                # Note that there's no pagination config for
                # 'TestOperation', indicating that TestOperation
                # is not pageable.
                'SomeOtherOperation': {
                    "input_token": "Marker",
                    "output_token": "Marker",
                    "more_results": "IsTruncated",
                    "limit_key": "MaxItems",
                    "result_key": "Users"
                }
            }
        }
        self.loader.load_data.return_value = pagination_config
        creator = client.ClientCreator(self.loader, endpoint_creator)
        service_client = creator.create_client('myservice', 'us-west-2')
        self.assertFalse(service_client.can_paginate('test_operation'))

    def test_operation_can_paginate(self):
        endpoint_creator = mock.Mock()
        pagination_config = {
            'pagination': {
                'TestOperation': {
                    "input_token": "Marker",
                    "output_token": "Marker",
                    "more_results": "IsTruncated",
                    "limit_key": "MaxItems",
                    "result_key": "Users"
                }
            }
        }
        self.loader.load_data.return_value = pagination_config
        creator = client.ClientCreator(self.loader, endpoint_creator)
        service_client = creator.create_client('myservice', 'us-west-2')
        self.assertTrue(service_client.can_paginate('test_operation'))
        # Also, the config is cached, but we want to make sure we get
        # the same answer when we ask again.
        self.assertTrue(service_client.can_paginate('test_operation'))

    def test_service_has_no_pagination_configs(self):
        # This is the case where there is an actual *.paginator.json, file,
        # but the specific operation itself is not actually pageable.
        endpoint_creator = mock.Mock()
        # If the loader cannot load pagination configs, it communicates
        # this by raising a DataNotFoundError.
        self.loader.load_data.side_effect = exceptions.DataNotFoundError(
            data_path='/foo')
        creator = client.ClientCreator(self.loader, endpoint_creator)
        service_client = creator.create_client('myservice', 'us-west-2')
        self.assertFalse(service_client.can_paginate('test_operation'))

    def test_try_to_paginate_non_paginated(self):
        endpoint_creator = mock.Mock()
        self.loader.load_data.side_effect = exceptions.DataNotFoundError(
            data_path='/foo')
        creator = client.ClientCreator(self.loader, endpoint_creator)
        service_client = creator.create_client('myservice', 'us-west-2')
        with self.assertRaises(exceptions.OperationNotPageableError):
            service_client.get_paginator('test_operation')

    def test_successful_pagination_object_created(self):
        endpoint_creator = mock.Mock()
        pagination_config = {
            'pagination': {
                'TestOperation': {
                    "input_token": "Marker",
                    "output_token": "Marker",
                    "more_results": "IsTruncated",
                    "limit_key": "MaxItems",
                    "result_key": "Users"
                }
            }
        }
        self.loader.load_data.return_value = pagination_config
        creator = client.ClientCreator(self.loader, endpoint_creator)
        service_client = creator.create_client('myservice', 'us-west-2')
        paginator = service_client.get_paginator('test_operation')
        # The pagination logic itself is tested elsewhere (test_paginate.py),
        # but we can at least make sure it looks like a paginator.
        self.assertTrue(hasattr(paginator, 'paginate'))
