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
"""
This module contains the main interface to the botocore package, the
Session object.
"""

import logging
import platform
import os
import copy
import shlex

import botocore.config
import botocore.credentials
import botocore.base
import botocore.service
from botocore.exceptions import ConfigNotFound, EventNotFound
from botocore.hooks import HierarchicalEmitter
from botocore import __version__
from botocore import handlers


AllEvents = {
    'after-call': '.%s.%s',
    'after-parsed': '.%s.%s.%s.%s',
    'before-call': '.%s.%s',
    'service-created': ''
    }
"""
A dictionary where each key is an event name and the value
is the formatting string used to construct a new event.
"""


EnvironmentVariables = {
    'profile': (None, 'BOTO_DEFAULT_PROFILE', 'default'),
    'region': ('region', 'BOTO_DEFAULT_REGION', None),
    'data_path': ('data_path', 'BOTO_DATA_PATH', None),
    'config_file': (None, 'AWS_CONFIG_FILE', '~/.aws/config'),
    'access_key': ('aws_access_key_id', 'AWS_ACCESS_KEY_ID', None),
    'secret_key': ('aws_secret_access_key', 'AWS_SECRET_ACCESS_KEY', None),
    'token': ('aws_security_token', 'AWS_SECURITY_TOKEN', None),
    'provider': ('provider', 'BOTO_PROVIDER_NAME', 'aws')
    }
"""
A default dictionary that maps the logical names for session variables
to the specific environment variables and configuration file names
that contain the values for these variables.

When creating a new Session object, you can pass in your own
dictionary to remap the logical names or to add new logical names.
You can then get the current value for these variables by using the
``get_variable`` method of the :class:`botocore.session.Session` class.
The default set of logical variable names are:

* profile - Default profile name you want to use.
* region - Default region name to use, if not otherwise specified.
* data_path - Additional directories to search for data files.
* config_file - Location of a Boto config file.
* access_key - The AWS access key part of your credentials.
* secret_key - The AWS secret key part of your credentials.
* token - The security token part of your credentials (session tokens only)
* provider - The name of the service provider (e.g. aws)

These form the keys of the dictionary.  The values in the dictionary
are tuples of (<config_name>, <environment variable>, <default value).
The ``profile`` and ``config_file`` variables should always have a
None value for the first entry in the tuple because it doesn't make
sense to look inside the config file for the location of the config
file or for the default profile to use.

The ``config_name`` is the name to look for in the configuration file,
the ``env var`` is the OS environment variable (``os.environ``) to
use, and ``default_value`` is the value to use if no value is otherwise
found.
"""


class Session(object):
    """
    The Session object collects together useful functionality
    from `botocore` as well as important data such as configuration
    information and credentials into a single, easy-to-use object.

    :ivar available_profiles: A list of profiles defined in the config
        file associated with this session.
    :ivar profile: The current profile.
    """

    FmtString = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    def __init__(self, env_vars=None, event_hooks=None,
                 include_builtin_handlers=True):
        """
        Create a new Session object.

        :type env_vars: dict
        :param env_vars: A dictionary that is used to override some or all
            of the environment variables associated with this session.  The
            key/value pairs defined in this dictionary will override the
            corresponding variables defined in ``EnvironmentVariables``.

        :type event_hooks: BaseEventHooks
        :param event_hooks: The event hooks object to use. If one is not
            provided, an event hooks object will be automatically created
            for you.

        :type include_builtin_handlers: bool
        :param include_builtin_handlers: Indicates whether or not to
            automatically register builtin handlers.
        """
        self.env_vars = copy.copy(EnvironmentVariables)
        if env_vars:
            self.env_vars.update(env_vars)
        if event_hooks is None:
            self._events = HierarchicalEmitter()
        else:
            self._events = event_hooks
        if include_builtin_handlers:
            self._register_builtin_handlers(self._events)
        self.user_agent_name = 'Boto'
        self.user_agent_version = __version__
        self._profile = None
        self._config = None
        self._credentials = None
        self._profile_map = None

    def _register_builtin_handlers(self, events):
        for event_name, handler in handlers.BUILTIN_HANDLERS:
            self.register(event_name, handler)

    @property
    def available_profiles(self):
        return list(self._build_profile_map().keys())

    def _build_profile_map(self):
        # This will build the profile map if it has not been created,
        # otherwise it will return the cached value.  The profile map
        # is a list of profile names, to the config values for the profile.
        if self._profile_map is None:
            profile_map = {}
            for key, values in self.full_config.items():
                if key.startswith("profile"):
                    try:
                        parts = shlex.split(key)
                    except ValueError:
                        continue
                    if len(parts) == 2:
                        profile_map[parts[1]] = values
                elif key == 'default':
                    # default section is special and is considered a profile
                    # name but we don't require you use 'profile "default"'
                    # as a section.
                    profile_map[key] = values
            self._profile_map = profile_map
        return self._profile_map

    @property
    def profile(self):
        return self._profile

    @profile.setter
    def profile(self, profile):
        self._profile = profile

    def get_variable(self, logical_name, methods=('env', 'config')):
        """
        Retrieve the value associated with the specified logical_name
        from the environment or the config file.  Values found in the
        environment variable take precedence of values found in the
        config file.  If no value can be found, a None will be returned.

        :type logical_name: str
        :param logical_name: The logical name of the session variable
            you want to retrieve.  This name will be mapped to the
            appropriate environment variable name for this session as
            well as the appropriate config file entry.

        :type method: tuple
        :param method: Defines which methods will be used to find
            the variable value.  By default, all available methods
            are tried but you can limit which methods are used
            by supplying a different value to this parameter.
            Valid choices are: both|env|config

        :returns: str value of variable of None if not defined.
        """
        value = None
        if logical_name in self.env_vars:
            config_name, envvar_name, default = self.env_vars[logical_name]
            if logical_name in ('config_file', 'profile'):
                config_name = None
            if logical_name == 'profile' and self._profile:
                value = self._profile
            elif 'env' in methods and envvar_name and envvar_name in os.environ:
                value = os.environ[envvar_name]
            elif 'config' in methods:
                if config_name:
                    config = self.get_config()
                    value = config.get(config_name, default)
        if value is None and default is not None:
            value = default
        return value

    def get_config(self):
        """
        Returns the configuration associated with this session.  If
        the configuration has not yet been loaded, it will be loaded
        using the default ``profile`` session variable.  If it has already been
        loaded, the cached configuration will be returned.

        Note that this configuration is specific to a single profile (the
        ``profile`` session variable).


        :raises: ConfigNotFound, ConfigParseError
        :rtype: dict
        """
        config = self.full_config
        profile_name = self.get_variable('profile')
        if not profile_name:
            profile_name = 'default'
        return self._build_profile_map().get(profile_name, {})

    @property
    def full_config(self):
        """Return the parsed config file.

        The ``get_config`` method returns the config associated with the
        specified profile.  This property returns the contents of the
        **entire** config file.

        :rtype: dict
        """
        if self._config is None:
            try:
                self._config = botocore.config.get_config(self)
            except ConfigNotFound:
                self._config = {}
        return self._config

    def set_credentials(self, access_key, secret_key, token=None):
        """
        Manually create credentials for this session.  If you would
        prefer to use botocore without a config file, environment variables,
        or IAM roles, you can pass explicit credentials into this
        method to establish credentials for this session.

        :type access_key: str
        :param access_key: The access key part of the credentials.

        :type secret_key: str
        :param secret_key: The secret key part of the credentials.

        :type token: str
        :param token: An option session token used by STS session
            credentials.
        """
        self._credentials = botocore.credentials.Credentials(access_key,
                                                             secret_key,
                                                             token)
        self._credentials.method = 'explicit'

    def get_credentials(self, metadata=None):
        """
        Return the :class:`botocore.credential.Credential` object
        associated with this session.  If the credentials have not
        yet been loaded, this will attempt to load them.  If they
        have already been loaded, this will return the cached
        credentials.

        :type metadata: dict
        :param metadata: This parameter allows you to pass in
            EC2 instance metadata containing IAM Role credentials.
            This metadata will be used rather than retrieving the
            metadata from the metadata service.  This is mainly used
            for unit testing.
        """
        if self._credentials is None:
            self._credentials = botocore.credentials.get_credentials(self,
                                                                     metadata)
        return self._credentials

    def user_agent(self):
        """
        Return a string suitable for use as a User-Agent header.
        The string will be of the form:

        <agent_name>/<agent_version> Python/<py_ver> <plat_name>/<plat_ver>

        Where:

         - agent_name is the value of the `user_agent_name` attribute
           of the session object (`Boto` by default).
         - agent_version is the value of the `user_agent_version`
           attribute of the session object (the botocore version by default).
           by default.
         - py_ver is the version of the Python interpreter beng used.
         - plat_name is the name of the platform (e.g. Darwin)
         - plat_ver is the version of the platform

        """
        return '%s/%s Python/%s %s/%s' % (self.user_agent_name,
                                          self.user_agent_version,
                                          platform.python_version(),
                                          platform.system(),
                                          platform.release())

    def get_data(self, data_path):
        """
        Retrieve the data associated with `data_path`.

        :type data_path: str
        :param data_path: The path to the data you wish to retrieve.
        """
        return botocore.base.get_data(self, data_path)

    def get_service_data(self, service_name, provider_name='aws'):
        """
        Retrieve the fully merged data associated with a service.
        """
        data_path = '%s/%s' % (provider_name, service_name)
        service_data = self.get_data(data_path)
        return service_data

    def get_available_services(self, provider_name='aws'):
        """
        Return a list of names of available services.
        """
        data_path = '%s' % provider_name
        return self.get_data(data_path)

    def get_service(self, service_name, provider_name='aws'):
        """
        Get information about a service.

        :type service_name: str
        :param service_name: The name of the service (e.g. 'ec2')

        :type provider_name: str
        :param provider_name: The name of the provider.  Defaults
            to 'aws'.

        :returns: :class:`botocore.service.Service`
        """
        service = botocore.service.get_service(self, service_name,
                                               provider_name)
        event = self.create_event('service-created')
        self._events.emit(event, service=service)
        return service

    def set_debug_logger(self):
        """
        Convenience function to quickly configure full debug output
        to go to the console.
        """
        log = logging.getLogger('botocore')
        log.setLevel(logging.DEBUG)

        # create console handler and set level to debug
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

        # create formatter
        formatter = logging.Formatter(self.FmtString)

        # add formatter to ch
        ch.setFormatter(formatter)

        # add ch to logger
        log.addHandler(ch)

    def set_file_logger(self, log_level, path):
        """
        Convenience function to quickly configure any level of logging
        to a file.

        :type log_level: int
        :param log_level: A log level as specified in the `logging` module

        :type path: string
        :param path: Path to the log file.  The file will be created
            if it doesn't already exist.
        """
        log = logging.getLogger('botocore')
        log.setLevel(log_level)

        # create console handler and set level to debug
        ch = logging.FileHandler(path)
        ch.setLevel(log_level)

        # create formatter
        formatter = logging.Formatter(self.FmtString)

        # add formatter to ch
        ch.setFormatter(formatter)

        # add ch to logger
        log.addHandler(ch)

    def register(self, event_name, handler):
        """Register a handler with an event.

        :type event_name: str
        :param event_name: The name of the event.

        :type handler: callable
        :param handler: The callback to invoke when the event
            is emitted.  This object must be callable, and must
            accept ``**kwargs``.  If either of these preconditions are
            not met, a ``ValueError`` will be raised.

        """
        self._events.register(event_name, handler)

    def unregister(self, event_name, handler):
        """Unregister a handler with an event.

        :type event_name: str
        :param event_name: The name of the event.

        :type handler: callable
        :param handler: The callback to unregister.

        """
        self._events.unregister(event_name, handler)

    def create_event(self, event_name, *fmtargs):
        """
        Creates a new event string that can then be emitted.
        You could just create it manually, since it's just
        a string but this helps to define the range of known events.

        :type event_name: str
        :param event_name: The base name of the new event.

        :type fmtargs: tuple
        :param fmtargs: A tuple of values that will be used as the
            arguments pass to the string formatting operation.  The
            actual values passed depend on the type of event you
            are creating.
        """
        if event_name in AllEvents:
            fmt_string = AllEvents[event_name]
            if fmt_string:
                event = event_name + (fmt_string % fmtargs)
            else:
                event = event_name
            return event
        raise EventNotFound(event_name=event_name)

    def emit(self, event_name, **kwargs):
        return self._events.emit(event_name, **kwargs)


def get_session(env_vars=None):
    """
    Return a new session object.
    """
    return Session(env_vars)
