# Copyright (c) 2012-2013 Mitch Garnaat http://garnaat.org/
# Copyright 2012-2014 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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

import logging

from .endpoint import get_endpoint
from .operation import Operation
from .waiter import Waiter
from .exceptions import ServiceNotInRegionError, NoRegionError


logger = logging.getLogger(__name__)


class Service(object):
    """
    A service, such as Elastic Compute Cloud (EC2).

    :ivar api_version: A string containing the API version this service
        is using.
    :ivar name: The full name of the service.
    :ivar service_name: The canonical name of the service.
    :ivar regions: A dict where each key is a region name and the
        optional value is an endpoint for that region.
    :ivar protocols: A list of protocols supported by the service.
    """
    WAITER_CLASS = Waiter

    def __init__(self, session, provider, service_name,
                 path='/', port=None, api_version=None):
        self.global_endpoint = None
        self.timestamp_format = 'iso8601'
        self.api_version = api_version
        sdata = session.get_service_data(
            service_name,
            api_version=self.api_version
        )
        self.__dict__.update(sdata)
        self._operations_data = self.__dict__.pop('operations')
        self._operations = None
        self.session = session
        self.provider = provider
        self.path = path
        self.port = port
        self.cli_name = service_name
        if not hasattr(self, 'metadata'):
            # metadata is an option thing that comes from .extra.json
            # so if it's not there we just default to an empty dict.
            self.metadata = {}

    def _create_operation_objects(self):
        logger.debug("Creating operation objects for: %s", self)
        operations = []
        for operation_name in self._operations_data:
            data = self._operations_data[operation_name]
            data['name'] = operation_name
            op = Operation(self, data)
            operations.append(op)
        return operations

    def __repr__(self):
        return 'Service(%s)' % self.endpoint_prefix

    @property
    def operations(self):
        if self._operations is None:
            self._operations = self._create_operation_objects()
        return self._operations

    @property
    def region_names(self):
        return self.metadata.get('regions', {}).keys()

    def _build_endpoint_url(self, host, is_secure):
        if is_secure:
            scheme = 'https'
        else:
            scheme = 'http'
        if scheme not in self.metadata['protocols']:
            raise ValueError('Unsupported protocol: %s' % scheme)
        endpoint_url = '%s://%s%s' % (scheme, host, self.path)
        if self.port:
            endpoint_url += ':%d' % self.port
        return endpoint_url

    def get_endpoint(self, region_name=None, is_secure=True,
                     endpoint_url=None, verify=None):
        """
        Return the Endpoint object for this service in a particular
        region.

        :type region_name: str
        :param region_name: The name of the region.

        :type is_secure: bool
        :param is_secure: True if you want the secure (HTTPS) endpoint.

        :type endpoint_url: str
        :param endpoint_url: You can explicitly override the default
            computed endpoint name with this parameter.  If this arg is
            provided then neither ``region_name`` nor ``is_secure``
            is used in building the final ``endpoint_url``.
            ``region_name`` can still be useful for services that require
            a region name independent of the endpoint_url (for example services
            that use Signature Version 4, which require a region name for
            use in the signature calculation).

        """
        if region_name is None:
            region_name = self.session.get_config_variable('region')
        if endpoint_url is not None:
            # Before getting into any of the region/endpoint
            # logic, if an endpoint_url is explicitly
            # provided, just use what's been explicitly passed in.
            return self._get_endpoint(region_name, endpoint_url, verify)
        # Use the endpoint resolver heuristics to build the endpoint url.
        resolver = self.session.get_component('endpoint_resolver')
        scheme = 'https' if is_secure else 'http'
        endpoint = resolver.construct_endpoint(
            self.endpoint_prefix, region_name, scheme=scheme)
        # We only support the credentialScope.region in the properties
        # bag right now, so if it's available, it will override the
        # provided region name.
        region_name_override = endpoint['properties'].get(
            'credentialScope', {}).get('region')
        if region_name_override is not None:
            region_name = region_name_override
        return self._get_endpoint(region_name, endpoint['uri'], verify)

    def _get_endpoint(self, region_name, endpoint_url, verify):
        # This function is called once we know the region and endpoint url.
        # region_name and endpoint_url are expected to be non-None.
        event = self.session.create_event('creating-endpoint',
                                          self.endpoint_prefix)
        self.session.emit(event, service=self, region_name=region_name,
                          endpoint_url=endpoint_url)
        return get_endpoint(self, region_name, endpoint_url, verify)

    def get_operation(self, operation_name):
        """
        Find an Operation object for a given operation_name.  The name
        provided can be the original camel case name, the Python name or
        the CLI name.

        :type operation_name: str
        :param operation_name: The name of the operation.
        """
        for operation in self.operations:
            op_names = (operation.name, operation.py_name, operation.cli_name)
            if operation_name in op_names:
                return operation
        return None

    def get_waiter(self, waiter_name):
        if waiter_name not in self.waiters:
            raise ValueError("Waiter does not exist: %s" % waiter_name)
        config = self.waiters[waiter_name]
        operation = self.get_operation(config['operation'])
        return self.WAITER_CLASS(waiter_name, operation, config)


def get_service(session, service_name, provider, api_version=None):
    """
    Return a Service object for a given provider name and service name.

    :type service_name: str
    :param service_name: The name of the service.

    :type provider: Provider
    :param provider: The Provider object associated with the session.
    """
    logger.debug("Creating service object for: %s", service_name)
    return Service(session, provider, service_name)
