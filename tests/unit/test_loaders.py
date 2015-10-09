# Copyright (c) 2013 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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

import os
import contextlib

import mock

from botocore.exceptions import DataNotFoundError, ValidationError
from botocore.loaders import JSONFileLoader
from botocore.loaders import Loader, create_loader

from tests import BaseEnvVar


class TestJSONFileLoader(BaseEnvVar):
    def setUp(self):
        super(TestJSONFileLoader, self).setUp()
        self.data_path = os.path.join(os.path.dirname(__file__), 'data')
        self.file_loader = JSONFileLoader()
        self.valid_file_path = os.path.join(self.data_path, 'foo')

    def test_load_file(self):
        data = self.file_loader.load_file(self.valid_file_path)
        self.assertEqual(len(data), 3)
        self.assertTrue('test_key_1' in data)

    def test_load_json_file_does_not_exist_returns_none(self):
        # None is used to indicate that the loader could not find a
        # file to load.
        self.assertIsNone(self.file_loader.load_file('fooasdfasdfasdf'))

    def test_file_exists_check(self):
        self.assertTrue(self.file_loader.exists(self.valid_file_path))

    def test_file_does_not_exist_returns_false(self):
        self.assertFalse(self.file_loader.exists(
            os.path.join(self.data_path, 'does', 'not', 'exist')))

    def test_file_with_non_ascii(self):
        try:
            filename = os.path.join(self.data_path, 'non_ascii')
            self.assertTrue(self.file_loader.load_file(filename) is not None)
        except UnicodeDecodeError:
            self.fail('Fail to handle data file with non-ascii characters')


class TestLoader(BaseEnvVar):

    def test_default_search_paths(self):
        loader = Loader()
        self.assertEqual(len(loader.search_paths), 2)
        # We should also have ~/.aws/models added to
        # the search path.  To deal with cross platform
        # issues we'll just check for a path that ends
        # with .aws/models.
        home_dir_path = os.path.join('.aws', 'models')
        self.assertTrue(
            any(p.endswith(home_dir_path) for p in
                loader.search_paths))

    def test_can_add_to_search_path(self):
        loader = Loader()
        loader.search_paths.append('mypath')
        self.assertIn('mypath', loader.search_paths)

    def test_can_initialize_with_search_paths(self):
        loader = Loader(extra_search_paths=['foo', 'bar'])
        self.assertIn('foo', loader.search_paths)
        self.assertIn('bar', loader.search_paths)
        # We should also always add the default search
        # paths even if the loader is initialized with
        # additional search paths.
        self.assertEqual(len(loader.search_paths), 4)

    # The file loader isn't consulted unless the current
    # search path exists, so we're patching isdir to always
    # say that a directory exists.
    @mock.patch('os.path.isdir', mock.Mock(return_value=True))
    def test_load_data_uses_loader(self):
        search_paths = ['foo', 'bar', 'baz']

        class FakeLoader(object):
            def load_file(self, name):
                expected_ending = os.path.join('bar', 'baz')
                if name.endswith(expected_ending):
                    return ['loaded data']

        loader = Loader(extra_search_paths=search_paths,
                        file_loader=FakeLoader())
        loaded = loader.load_data('baz')
        self.assertEqual(loaded, ['loaded data'])

    def test_data_not_found_raises_exception(self):
        class FakeLoader(object):
            def load_file(self, name):
                # Returning None indicates that the
                # loader couldn't find anything.
                return None
        loader = Loader(file_loader=FakeLoader())
        with self.assertRaises(DataNotFoundError):
            loader.load_data('baz')

    @mock.patch('os.path.isdir', mock.Mock(return_value=True))
    def test_error_raised_if_service_does_not_exist(self):
        loader = Loader(extra_search_paths=[],
                        include_default_search_paths=False)
        with self.assertRaises(DataNotFoundError):
            loader.determine_latest_version('unknownservice', 'service-2')

    @mock.patch('os.path.isdir', mock.Mock(return_value=True))
    def test_load_service_model(self):
        class FakeLoader(object):
            def load_file(self, name):
                return ['loaded data']

        loader = Loader(extra_search_paths=['foo'],
                        file_loader=FakeLoader(),
                        include_default_search_paths=False)
        loader.determine_latest_version = mock.Mock(return_value='2015-03-01')
        loader.list_available_services = mock.Mock(return_value=['baz'])
        loaded = loader.load_service_model('baz', type_name='service-2')
        self.assertEqual(loaded, ['loaded data'])

    @mock.patch('os.path.isdir', mock.Mock(return_value=True))
    def test_load_service_model_enforces_case(self):
        class FakeLoader(object):
            def load_file(self, name):
                return ['loaded data']

        loader = Loader(extra_search_paths=['foo'],
                        file_loader=FakeLoader(),
                        include_default_search_paths=False)
        loader.determine_latest_version = mock.Mock(return_value='2015-03-01')
        loader.list_available_services = mock.Mock(return_value=['baz'])

        with self.assertRaises(ValidationError):
            loader.load_service_model('BAZ', type_name='service-2')

    def test_create_loader_parses_data_path(self):
        search_path = os.pathsep.join(['foo', 'bar', 'baz'])
        loader = create_loader(search_path)
        self.assertIn('foo', loader.search_paths)
        self.assertIn('bar', loader.search_paths)
        self.assertIn('baz', loader.search_paths)


class TestLoadersWithDirectorySearching(BaseEnvVar):
    def setUp(self):
        super(TestLoadersWithDirectorySearching, self).setUp()
        self.fake_directories = {}

    def tearDown(self):
        super(TestLoadersWithDirectorySearching, self).tearDown()

    @contextlib.contextmanager
    def loader_with_fake_dirs(self):
        mock_file_loader = mock.Mock()
        mock_file_loader.exists = self.fake_exists
        search_paths = list(self.fake_directories)
        loader = Loader(extra_search_paths=search_paths,
                        include_default_search_paths=False,
                        file_loader=mock_file_loader)
        with mock.patch('os.listdir', self.fake_listdir):
            with mock.patch('os.path.isdir', mock.Mock(return_value=True)):
                yield loader


    def fake_listdir(self, dirname):
        parts = dirname.split(os.path.sep)
        result = self.fake_directories
        while parts:
            current = parts.pop(0)
            result = result[current]
        return list(result)

    def fake_exists(self, path):
        parts = path.split(os.sep)
        result = self.fake_directories
        while len(parts) > 1:
            current = parts.pop(0)
            result = result[current]
        return parts[0] in result

    def test_list_available_services(self):
        self.fake_directories = {
            'foo': {
                'ec2': {
                    '2010-01-01': ['service-2'],
                    '2014-10-01': ['service-1'],
                },
                'dynamodb': {
                    '2010-01-01': ['service-2'],
                },
            },
            'bar': {
                'ec2': {
                    '2015-03-01': ['service-1'],
                },
                'rds': {
                    # This will not show up in
                    # list_available_services() for type
                    # service-2 because it does not contains
                    # a service-2.
                    '2012-01-01': ['resource-1'],
                },
            },
        }
        with self.loader_with_fake_dirs() as loader:
            self.assertEqual(
                loader.list_available_services(type_name='service-2'),
                ['dynamodb', 'ec2'])
            self.assertEqual(
                loader.list_available_services(type_name='resource-1'),
                ['rds'])

    def test_determine_latest(self):
        # Fake mapping of directories to subdirectories.
        # In this example, we can see that the 'bar' directory
        # contains the latest EC2 API version, 2015-03-01,
        # so loader.determine_latest('ec2') should return
        # this value 2015-03-01.
        self.fake_directories = {
            'foo': {
                'ec2': {
                    '2010-01-01': ['service-2'],
                    # This directory contains the latest API version
                    # for EC2 because its the highest API directory
                    # that contains a service-2.
                    '2014-10-01': ['service-2'],
                },
            },
            'bar': {
                'ec2': {
                    '2012-01-01': ['service-2'],
                    # 2015-03-1 is *not* the latest for service-2,
                    # because its directory only has service-1.json.
                    '2015-03-01': ['service-1'],
                },
            },
        }
        with self.loader_with_fake_dirs() as loader:
            latest = loader.determine_latest_version('ec2', 'service-2')
            self.assertEqual(loader.determine_latest_version('ec2', 'service-2'),
                             '2014-10-01')
            self.assertEqual(loader.determine_latest_version('ec2', 'service-1'),
                             '2015-03-01')
