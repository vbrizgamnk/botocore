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


from .exceptions import InvalidExpressionError
from .compat import json
from .vendored import requests


logger = logging.getLogger(__name__)
DEFAULT_METADATA_SERVICE_TIMEOUT = 1
METADATA_SECURITY_CREDENTIALS_URL = (
    'http://169.254.169.254/latest/meta-data/iam/security-credentials/'
)


class _RetriesExceededError(Exception):
    """Internal exception used when the number of retries are exceeded."""
    pass


def normalize_url_path(path):
    if not path:
        return '/'
    return remove_dot_segments(path)


def remove_dot_segments(url):
    # RFC 2986, section 5.2.4 "Remove Dot Segments"
    output = []
    while url:
        if url.startswith('../'):
            url = url[3:]
        elif url.startswith('./'):
            url = url[2:]
        elif url.startswith('/./'):
            url = '/' + url[3:]
        elif url.startswith('/../'):
            url = '/' + url[4:]
            if output:
                output.pop()
        elif url.startswith('/..'):
            url = '/' + url[3:]
            if output:
                output.pop()
        elif url.startswith('/.'):
            url = '/' + url[2:]
        elif url == '.' or url == '..':
            url = ''
        elif url.startswith('//'):
            # As far as I can tell, this is not in the RFC,
            # but AWS auth services require consecutive
            # slashes are removed.
            url = url[1:]
        else:
            if url[0] == '/':
                next_slash = url.find('/', 1)
            else:
                next_slash = url.find('/', 0)
            if next_slash == -1:
                output.append(url)
                url = ''
            else:
                output.append(url[:next_slash])
                url = url[next_slash:]
    return ''.join(output)


def validate_jmespath_for_set(expression):
    # Validates a limited jmespath expression to determine if we can set a value
    # based on it. Only works with dotted paths.
    if not expression or expression == '.':
        raise InvalidExpressionError(expression=expression)

    for invalid in ['[', ']', '*']:
        if invalid in expression:
            raise InvalidExpressionError(expression=expression)


def set_value_from_jmespath(source, expression, value, is_first=True):
    # This takes a (limited) jmespath-like expression & can set a value based
    # on it.
    # Limitations:
    # * Only handles dotted lookups
    # * No offsets/wildcards/slices/etc.
    if is_first:
        validate_jmespath_for_set(expression)

    bits = expression.split('.', 1)
    current_key, remainder = bits[0], bits[1] if len(bits) > 1 else ''

    if not current_key:
        raise InvalidExpressionError(expression=expression)

    if remainder:
        if not current_key in source:
            # We've got something in the expression that's not present in the
            # source (new key). If there's any more bits, we'll set the key with
            # an empty dictionary.
            source[current_key] = {}

        return set_value_from_jmespath(
            source[current_key],
            remainder,
            value,
            is_first=False
        )

    # If we're down to a single key, set it.
    source[current_key] = value


class InstanceMetadataFetcher(object):
    def _get_request(self, url, timeout, num_attempts=1):
        for i in range(num_attempts):
            try:
                response = requests.get(url, timeout=timeout)
            except (requests.Timeout, requests.ConnectionError) as e:
                logger.debug("Caught exception while trying to retrieve "
                             "credentials: %s", e, exc_info=True)
            else:
                if response.status_code == 200:
                    return response
        raise _RetriesExceededError()

    def retrieve_iam_role_credentials(self,
                                      url=METADATA_SECURITY_CREDENTIALS_URL,
                                      timeout=None, num_attempts=1):
        if timeout is None:
            timeout = DEFAULT_METADATA_SERVICE_TIMEOUT
        data = {}
        try:
            r = self._get_request(url, timeout, num_attempts)
            if r.content:
                fields = r.content.decode('utf-8').split('\n')
                for field in fields:
                    if field.endswith('/'):
                        data[field[0:-1]] = self.retrieve_iam_role_credentials(
                            url + field, timeout, num_attempts)
                    else:
                        val = self._get_request(
                            url + field,
                            timeout=timeout,
                            num_attempts=num_attempts).content.decode('utf-8')
                        if val[0] == '{':
                            val = json.loads(val)
                        data[field] = val
            else:
                logger.debug("Metadata service returned non 200 status code "
                             "of %s for url: %s, content body: %s",
                             r.status_code, url, r.content)
        except _RetriesExceededError:
            logger.debug("Max number of attempts exceeded (%s) when "
                         "attempting to retrieve data from metadata service.",
                         num_attempts)
        # We sort for stable ordering. In practice, this should only consist
        # of one role, but may need revisiting if this expands in the future.
        final_data = {}
        for role_name in sorted(data):
            final_data = {
                'role_name': role_name,
                'access_key': data[role_name]['AccessKeyId'],
                'secret_key': data[role_name]['SecretAccessKey'],
                'token': data[role_name]['Token'],
                'expiry_time': data[role_name]['Expiration'],
            }
        return final_data
