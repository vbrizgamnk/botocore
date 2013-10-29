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
import os
from botocore.vendored import requests
import logging

from six.moves import configparser

from botocore.compat import json


logger = logging.getLogger(__name__)


class Credentials(object):
    """
    Holds the credentials needed to authenticate requests.  In addition
    the Credential object knows how to search for credentials and how
    to choose the right credentials when multiple credentials are found.

    :ivar access_key: The access key part of the credentials.
    :ivar secret_key: The secret key part of the credentials.
    :ivar token: The security token, valid only for session credentials.
    :ivar method: A string which identifies where the credentials
        were found.  Valid values are: iam_role|env|config|boto.
    """

    def __init__(self, access_key=None, secret_key=None, token=None):
        self.access_key = access_key
        self.secret_key = secret_key
        self.token = token
        self.method = None
        self.profiles = []


def _search_md(url='http://169.254.169.254/latest/meta-data/iam/security-credentials/'):
    d = {}
    try:
        r = requests.get(url, timeout=.1)
        if r.status_code == 200 and r.content:
            fields = r.content.decode('utf-8').split('\n')
            for field in fields:
                if field.endswith('/'):
                    d[field[0:-1]] = _search_md(url + field)
                else:
                    val = requests.get(url + field).content.decode('utf-8')
                    if val[0] == '{':
                        val = json.loads(val)
                    else:
                        p = val.find('\n')
                        if p > 0:
                            val = r.content.decode('utf-8').split('\n')
                    d[field] = val
    except (requests.Timeout, requests.ConnectionError):
        pass
    return d


def search_iam_role(**kwargs):
    credentials = None
    metadata = kwargs.get('metadata', None)
    if metadata is None:
        metadata = _search_md()
    if metadata:
        for role_name in metadata:
            credentials = Credentials(metadata[role_name]['AccessKeyId'],
                                      metadata[role_name]['SecretAccessKey'],
                                      metadata[role_name]['Token'])
            credentials.method = 'iam-role'
            logger.info('Found IAM Role: %s', role_name)
    return credentials


def search_environment(**kwargs):
    """
    Search for credentials in explicit environment variables.
    """
    session = kwargs.get('session')
    credentials = None
    access_key = session.get_variable('access_key', ('env',))
    secret_key = session.get_variable('secret_key', ('env',))
    token = session.get_variable('token', ('env',))
    if access_key and secret_key:
        credentials = Credentials(access_key, secret_key, token)
        credentials.method = 'env'
        logger.info('Found credentials in Environment variables.')
    return credentials


def search_credentials_file(**kwargs):
    """
    Search for a credential file used by original EC2 CLI tools.
    """
    credentials = None
    if 'AWS_CREDENTIAL_FILE' in os.environ:
        full_path = os.path.expanduser(os.environ['AWS_CREDENTIAL_FILE'])
        try:
            lines = map(str.strip, open(full_path).readlines())
        except IOError:
            logger.warn('Unable to load AWS_CREDENTIAL_FILE (%s).', full_path)
        else:
            config = dict(line.split('=', 1) for line in lines if '=' in line)
            access_key = config.get('AWSAccessKeyId')
            secret_key = config.get('AWSSecretKey')
            if access_key and secret_key:
                credentials = Credentials(access_key, secret_key)
                credentials.method = 'credentials-file'
                logger.info('Found credentials in AWS_CREDENTIAL_FILE.')
    return credentials


def search_file(**kwargs):
    """
    If there is are credentials in the configuration associated with
    the session, use those.
    """
    credentials = None
    session = kwargs.get('session')
    access_key = session.get_variable('access_key', methods=('config',))
    secret_key = session.get_variable('secret_key', methods=('config',))
    token = session.get_variable('token', ('config',))
    if access_key and secret_key:
        credentials = Credentials(access_key, secret_key, token)
        credentials.method = 'config'
        logger.info('Found credentials in config file.')
    return credentials


def search_boto_config(**kwargs):
    """
    Look for credentials in boto config file.
    """
    credentials = access_key = secret_key = None
    if 'BOTO_CONFIG' in os.environ:
        paths = [os.environ['BOTO_CONFIG']]
    else:
        paths = ['/etc/boto.cfg', '~/.boto']
    paths = [os.path.expandvars(p) for p in paths]
    paths = [os.path.expanduser(p) for p in paths]
    cp = configparser.RawConfigParser()
    cp.read(paths)
    if cp.has_section('Credentials'):
        if cp.has_option('Credentials', 'aws_access_key_id'):
            access_key = cp.get('Credentials', 'aws_access_key_id')
        if cp.has_option('Credentials', 'aws_secret_access_key'):
            secret_key = cp.get('Credentials', 'aws_secret_access_key')
    if access_key and secret_key:
        credentials = Credentials(access_key, secret_key)
        credentials.method = 'boto'
        logger.info('Found credentials in boto config file.')
    return credentials

AllCredentialFunctions = [search_environment,
                          search_credentials_file,
                          search_file,
                          search_boto_config,
                          search_iam_role]

_credential_methods = (('env', search_environment),
                       ('config', search_file),
                       ('credentials-file', search_credentials_file),
                       ('boto', search_boto_config),
                       ('iam-role', search_iam_role))


def get_credentials(session, metadata=None):
    credentials = None
    for cred_method, cred_fn in _credential_methods:
        credentials = cred_fn(session=session,
                              metadata=metadata)
        if credentials:
            break
    return credentials
