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

from tests import unittest
from botocore.paginate import Paginator
from botocore.paginate import PaginatorModel
from botocore.exceptions import PaginationError

import mock


class TestPaginatorModel(unittest.TestCase):
    def setUp(self):
        self.paginator_config = {}
        self.paginator_config['pagination'] = {
            'ListFoos': {
                'output_token': 'NextToken',
                'input_token': 'NextToken',
                'result_key': 'Foo'
            }
        }
        self.paginator_model = PaginatorModel(self.paginator_config)

    def test_get_paginator(self):
        paginator_config = self.paginator_model.get_paginator('ListFoos')
        self.assertEqual(
            paginator_config,
            {'output_token': 'NextToken', 'input_token': 'NextToken',
             'result_key': 'Foo'}
        )

    def test_get_paginator_no_exists(self):
        with self.assertRaises(ValueError):
            paginator_config = self.paginator_model.get_paginator('ListBars')


class TestPagination(unittest.TestCase):
    def setUp(self):
        self.method = mock.Mock()
        self.paginate_config = {
            'output_token': 'NextToken',
            'input_token': 'NextToken',
            'result_key': 'Foo',
        }
        self.paginator = Paginator(self.method, self.paginate_config)

    def test_result_key_available(self):
        self.assertEqual(
            [rk.expression for rk in self.paginator.result_keys],
            ['Foo']
        )

    def test_no_next_token(self):
        response = {'not_the_next_token': 'foobar'}
        self.method.return_value = response
        actual = list(self.paginator.paginate())
        self.assertEqual(actual, [{'not_the_next_token': 'foobar'}])

    def test_next_token_in_response(self):
        responses = [{'NextToken': 'token1'},
                     {'NextToken': 'token2'},
                     {'not_next_token': 'foo'}]
        self.method.side_effect = responses
        actual = list(self.paginator.paginate())
        self.assertEqual(actual, responses)
        # The first call has no next token, the second and third call should
        # have 'token1' and 'token2' respectively.
        self.assertEqual(self.method.call_args_list,
                         [mock.call(), mock.call(NextToken='token1'),
                          mock.call(NextToken='token2')])

    def test_any_passed_in_args_are_unmodified(self):
        responses = [{'NextToken': 'token1'},
                     {'NextToken': 'token2'},
                     {'not_next_token': 'foo'}]
        self.method.side_effect = responses
        actual = list(self.paginator.paginate(Foo='foo', Bar='bar'))
        self.assertEqual(actual, responses)
        self.assertEqual(
            self.method.call_args_list,
            [mock.call(Foo='foo', Bar='bar'),
             mock.call(Foo='foo', Bar='bar', NextToken='token1'),
             mock.call(Foo='foo', Bar='bar', NextToken='token2')])

    def test_exception_raised_if_same_next_token(self):
        responses = [{'NextToken': 'token1'},
                     {'NextToken': 'token2'},
                     {'NextToken': 'token2'}]
        self.method.side_effect = responses
        with self.assertRaises(PaginationError):
            list(self.paginator.paginate())

    def test_next_token_with_or_expression(self):
        self.pagination_config = {
            'output_token': 'NextToken || NextToken2',
            'input_token': 'NextToken',
            'result_key': 'Foo',
        }
        self.paginator = Paginator(self.method, self.pagination_config)
        # Verify that despite varying between NextToken and NextToken2
        # we still can extract the right next tokens.
        responses = [
            {'NextToken': 'token1'},
            {'NextToken2': 'token2'},
            # The first match found wins, so because NextToken is
            # listed before NextToken2 in the 'output_tokens' config,
            # 'token3' is chosen over 'token4'.
            {'NextToken': 'token3', 'NextToken2': 'token4'},
            {'not_next_token': 'foo'},
        ]
        self.method.side_effect = responses
        list(self.paginator.paginate())
        self.assertEqual(
            self.method.call_args_list,
            [mock.call(),
             mock.call(NextToken='token1'),
             mock.call(NextToken='token2'),
             mock.call(NextToken='token3')])

    def test_more_tokens(self):
        # Some pagination configs have a 'more_token' key that
        # indicate whether or not the results are being paginated.
        self.paginate_config = {
            'more_results': 'IsTruncated',
            'output_token': 'NextToken',
            'input_token': 'NextToken',
            'result_key': 'Foo',
        }
        self.paginator = Paginator(self.method, self.paginate_config)
        responses = [
            {'Foo': [1], 'IsTruncated': True, 'NextToken': 'token1'},
            {'Foo': [2], 'IsTruncated': True, 'NextToken': 'token2'},
            {'Foo': [3], 'IsTruncated': False, 'NextToken': 'token3'},
            {'Foo': [4], 'not_next_token': 'foo'},
        ]
        self.method.side_effect = responses
        list(self.paginator.paginate())
        self.assertEqual(
            self.method.call_args_list,
            [mock.call(),
             mock.call(NextToken='token1'),
             mock.call(NextToken='token2')])

    def test_more_tokens_is_path_expression(self):
        self.paginate_config = {
            'more_results': 'Foo.IsTruncated',
            'output_token': 'NextToken',
            'input_token': 'NextToken',
            'result_key': 'Bar',
        }
        self.paginator = Paginator(self.method, self.paginate_config)
        responses = [
            {'Foo': {'IsTruncated': True}, 'NextToken': 'token1'},
            {'Foo': {'IsTruncated': False}, 'NextToken': 'token2'},
        ]
        self.method.side_effect = responses
        list(self.paginator.paginate())
        self.assertEqual(
            self.method.call_args_list,
            [mock.call(),
             mock.call(NextToken='token1')])

    def test_page_size(self):
        self.paginate_config = {
            "output_token": "Marker",
            "input_token": "Marker",
            "result_key": "Users",
            "limit_key": "MaxKeys",
        }
        self.paginator = Paginator(self.method, self.paginate_config)
        responses = [
            {"Users": ["User1"], "Marker": "m1"},
            {"Users": ["User2"], "Marker": "m2"},
            {"Users": ["User3"]},
        ]
        self.method.side_effect = responses
        users = []
        for page in self.paginator.paginate(PaginationConfig={'PageSize': 1}):
            users += page['Users']
        self.assertEqual(
            self.method.call_args_list,
            [mock.call(MaxKeys=1),
             mock.call(Marker='m1', MaxKeys=1),
             mock.call(Marker='m2', MaxKeys=1)]
        )

    def test_with_empty_markers(self):
        responses = [
            {"Users": ["User1"], "Marker": ""},
            {"Users": ["User1"], "Marker": ""},
            {"Users": ["User1"], "Marker": ""}
        ]
        self.method.side_effect = responses
        users = []
        for page in self.paginator.paginate():
            users += page['Users']
        # We want to stop paginating if the next token is empty.
        self.assertEqual(
            self.method.call_args_list,
            [mock.call()]
        )
        self.assertEqual(users, ['User1'])

    def test_build_full_result_with_single_key(self):
        self.paginate_config = {
            "output_token": "Marker",
            "input_token": "Marker",
            "result_key": "Users",
            "limit_key": "MaxKeys",
        }
        self.paginator = Paginator(self.method, self.paginate_config)
        responses = [
            {"Users": ["User1"], "Marker": "m1"},
            {"Users": ["User2"], "Marker": "m2"},
            {"Users": ["User3"]}
        ]
        self.method.side_effect = responses
        pages = self.paginator.paginate()
        complete = pages.build_full_result()
        self.assertEqual(complete, {'Users': ['User1', 'User2', 'User3']})


class TestPaginatorPageSize(unittest.TestCase):
    def setUp(self):
        self.method = mock.Mock()
        self.paginate_config = {
            "output_token": "Marker",
            "input_token": "Marker",
            "result_key": ["Users", "Groups"],
            'limit_key': 'MaxKeys',
        }
        self.paginator = Paginator(self.method, self.paginate_config)
        self.endpoint = mock.Mock()

    def test_no_page_size(self):
        kwargs = {'arg1': 'foo', 'arg2': 'bar'}
        ref_kwargs = {'arg1': 'foo', 'arg2': 'bar'}
        pages = self.paginator.paginate(**kwargs)
        pages._inject_starting_params(kwargs)
        self.assertEqual(kwargs, ref_kwargs)

    def test_page_size(self):
        kwargs = {'arg1': 'foo', 'arg2': 'bar',
                  'PaginationConfig': {'PageSize': 5}}
        extracted_kwargs = {'arg1': 'foo', 'arg2': 'bar'}
        # Note that ``MaxKeys`` in ``setUp()`` is the parameter used for
        # the page size for pagination.
        ref_kwargs = {'arg1': 'foo', 'arg2': 'bar', 'MaxKeys': 5}
        pages = self.paginator.paginate(**kwargs)
        pages._inject_starting_params(extracted_kwargs)
        self.assertEqual(extracted_kwargs, ref_kwargs)


class TestPaginatorWithPathExpressions(unittest.TestCase):
    def setUp(self):
        self.method = mock.Mock()
        # This is something we'd see in s3 pagination.
        self.paginate_config = {
            'output_token': [
                'NextMarker || ListBucketResult.Contents[-1].Key'],
            'input_token': 'next_marker',
            'result_key': 'Contents',
        }
        self.paginator = Paginator(self.method, self.paginate_config)

    def test_s3_list_objects(self):
        responses = [
            {'NextMarker': 'token1'},
            {'NextMarker': 'token2'},
            {'not_next_token': 'foo'}]
        self.method.side_effect = responses
        list(self.paginator.paginate())
        self.assertEqual(
            self.method.call_args_list,
            [mock.call(),
             mock.call(next_marker='token1'),
             mock.call(next_marker='token2')])

    def test_s3_list_object_complex(self):
        responses = [
            {'NextMarker': 'token1'},
            {'ListBucketResult': {
                'Contents': [{"Key": "first"}, {"Key": "Last"}]}},
            {'not_next_token': 'foo'}]
        self.method.side_effect = responses
        list(self.paginator.paginate())
        self.assertEqual(
            self.method.call_args_list,
            [mock.call(),
             mock.call(next_marker='token1'),
             mock.call(next_marker='Last')])


class TestMultipleTokens(unittest.TestCase):
    def setUp(self):
        self.method = mock.Mock()
        # This is something we'd see in s3 pagination.
        self.paginate_config = {
            "output_token": ["ListBucketResults.NextKeyMarker",
                             "ListBucketResults.NextUploadIdMarker"],
            "input_token": ["key_marker", "upload_id_marker"],
            "result_key": 'Foo',
        }
        self.paginator = Paginator(self.method, self.paginate_config)

    def test_s3_list_multipart_uploads(self):
        responses = [
            {"Foo": [1], "ListBucketResults": {"NextKeyMarker": "key1",
             "NextUploadIdMarker": "up1"}},
            {"Foo": [2], "ListBucketResults": {"NextKeyMarker": "key2",
             "NextUploadIdMarker": "up2"}},
            {"Foo": [3], "ListBucketResults": {"NextKeyMarker": "key3",
             "NextUploadIdMarker": "up3"}},
            {}
        ]
        self.method.side_effect = responses
        list(self.paginator.paginate())
        self.assertEqual(
            self.method.call_args_list,
            [mock.call(),
             mock.call(key_marker='key1', upload_id_marker='up1'),
             mock.call(key_marker='key2', upload_id_marker='up2'),
             mock.call(key_marker='key3', upload_id_marker='up3'),
             ])


class TestKeyIterators(unittest.TestCase):
    def setUp(self):
        self.method = mock.Mock()
        # This is something we'd see in s3 pagination.
        self.paginate_config = {
            "output_token": "Marker",
            "input_token": "Marker",
            "result_key": "Users"
        }
        self.paginator = Paginator(self.method, self.paginate_config)

    def test_result_key_iters(self):
        responses = [
            {"Users": ["User1"], "Marker": "m1"},
            {"Users": ["User2"], "Marker": "m2"},
            {"Users": ["User3"]},
        ]
        self.method.side_effect = responses
        pages = self.paginator.paginate()
        iterators = pages.result_key_iters()
        self.assertEqual(len(iterators), 1)
        self.assertEqual(list(iterators[0]),
                         ["User1", "User2", "User3"])

    def test_build_full_result_with_single_key(self):
        responses = [
            {"Users": ["User1"], "Marker": "m1"},
            {"Users": ["User2"], "Marker": "m2"},
            {"Users": ["User3"]},
        ]
        self.method.side_effect = responses
        pages = self.paginator.paginate()
        complete = pages.build_full_result()
        self.assertEqual(complete, {'Users': ['User1', 'User2', 'User3']})

    def test_max_items_can_be_specified(self):
        paginator = Paginator(self.method, self.paginate_config)
        responses = [
            {"Users": ["User1"], "Marker": "m1"},
            {"Users": ["User2"], "Marker": "m2"},
            {"Users": ["User3"]},
        ]
        self.method.side_effect = responses
        self.assertEqual(
            paginator.paginate(
                PaginationConfig={'MaxItems': 1}).build_full_result(),
            {'Users': ['User1'], 'NextToken': 'm1'})

    def test_max_items_as_strings(self):
        # Some services (route53) model MaxItems as a string type.
        # We need to be able to handle this case.
        paginator = Paginator(self.method, self.paginate_config)
        responses = [
            {"Users": ["User1"], "Marker": "m1"},
            {"Users": ["User2"], "Marker": "m2"},
            {"Users": ["User3"]},
        ]
        self.method.side_effect = responses
        self.assertEqual(
            # Note MaxItems is a string here.
            paginator.paginate(
                PaginationConfig={'MaxItems': '1'}).build_full_result(),
            {'Users': ['User1'], 'NextToken': 'm1'})

    def test_next_token_on_page_boundary(self):
        paginator = Paginator(self.method, self.paginate_config)
        responses = [
            {"Users": ["User1"], "Marker": "m1"},
            {"Users": ["User2"], "Marker": "m2"},
            {"Users": ["User3"]},
        ]
        self.method.side_effect = responses
        self.assertEqual(
            paginator.paginate(
                PaginationConfig={'MaxItems': 2}).build_full_result(),
            {'Users': ['User1', 'User2'], 'NextToken': 'm2'})

    def test_max_items_can_be_specified_truncates_response(self):
        # We're saying we only want 4 items, but notice that the second
        # page of results returns users 4-6 so we have to truncated
        # part of that second page.
        paginator = Paginator(self.method, self.paginate_config)
        responses = [
            {"Users": ["User1", "User2", "User3"], "Marker": "m1"},
            {"Users": ["User4", "User5", "User6"], "Marker": "m2"},
            {"Users": ["User7"]},
        ]
        self.method.side_effect = responses
        self.assertEqual(
            paginator.paginate(
                PaginationConfig={'MaxItems': 4}).build_full_result(),
            {'Users': ['User1', 'User2', 'User3', 'User4'],
             'NextToken': 'm1___1'})

    def test_resume_next_marker_mid_page(self):
        # This is a simulation of picking up from the response
        # from test_MaxItems_can_be_specified_truncates_response
        # We got the first 4 users, when we pick up we should get
        # User5 - User7.
        paginator = Paginator(self.method, self.paginate_config)
        responses = [
            {"Users": ["User4", "User5", "User6"], "Marker": "m2"},
            {"Users": ["User7"]},
        ]
        self.method.side_effect = responses
        pagination_config = {'StartingToken': 'm1___1'}
        self.assertEqual(
            paginator.paginate(
                PaginationConfig=pagination_config).build_full_result(),
            {'Users': ['User5', 'User6', 'User7']})
        self.assertEqual(
            self.method.call_args_list,
            [mock.call(Marker='m1'),
             mock.call(Marker='m2')])

    def test_max_items_exceeds_actual_amount(self):
        # Because MaxItems=10 > number of users (3), we should just return
        # all of the users.
        paginator = Paginator(self.method, self.paginate_config)
        responses = [
            {"Users": ["User1"], "Marker": "m1"},
            {"Users": ["User2"], "Marker": "m2"},
            {"Users": ["User3"]},
        ]
        self.method.side_effect = responses
        self.assertEqual(
            paginator.paginate(
                PaginationConfig={'MaxItems': 10}).build_full_result(),
            {'Users': ['User1', 'User2', 'User3']})

    def test_bad_input_tokens(self):
        responses = [
            {"Users": ["User1"], "Marker": "m1"},
            {"Users": ["User2"], "Marker": "m2"},
            {"Users": ["User3"]},
        ]
        self.method.side_effect = responses
        with self.assertRaisesRegexp(ValueError, 'Bad starting token'):
            pagination_config = {'StartingToken': 'bad___notanint'}
            self.paginator.paginate(
                PaginationConfig=pagination_config).build_full_result()


class TestMultipleResultKeys(unittest.TestCase):
    def setUp(self):
        self.method = mock.Mock()
        # This is something we'd see in s3 pagination.
        self.paginate_config = {
            "output_token": "Marker",
            "input_token": "Marker",
            "result_key": ["Users", "Groups"],
        }
        self.paginator = Paginator(self.method, self.paginate_config)

    def test_build_full_result_with_multiple_result_keys(self):
        responses = [
            {"Users": ["User1"], "Groups": ["Group1"], "Marker": "m1"},
            {"Users": ["User2"], "Groups": ["Group2"], "Marker": "m2"},
            {"Users": ["User3"], "Groups": ["Group3"]},
        ]
        self.method.side_effect = responses
        pages = self.paginator.paginate()
        complete = pages.build_full_result()
        self.assertEqual(complete,
                         {"Users": ['User1', 'User2', 'User3'],
                          "Groups": ['Group1', 'Group2', 'Group3']})

    def test_build_full_result_with_different_length_result_keys(self):
        responses = [
            {"Users": ["User1"], "Groups": ["Group1"], "Marker": "m1"},
            # Then we stop getting "Users" output, but we get more "Groups"
            {"Users": [], "Groups": ["Group2"], "Marker": "m2"},
            {"Users": [], "Groups": ["Group3"]},
        ]
        self.method.side_effect = responses
        pages = self.paginator.paginate()
        complete = pages.build_full_result()
        self.assertEqual(complete,
                         {"Users": ['User1'],
                          "Groups": ['Group1', 'Group2', 'Group3']})

    def test_build_full_result_with_zero_length_result_key(self):
        responses = [
            # In this case the 'Users' key is always empty but we should
            # have a 'Users' key in the output, it should just have an
            # empty list for a value.
            {"Users": [], "Groups": ["Group1"], "Marker": "m1"},
            {"Users": [], "Groups": ["Group2"], "Marker": "m2"},
            {"Users": [], "Groups": ["Group3"]},
        ]
        self.method.side_effect = responses
        pages = self.paginator.paginate()
        complete = pages.build_full_result()
        self.assertEqual(complete,
                         {"Users": [],
                          "Groups": ['Group1', 'Group2', 'Group3']})

    def test_build_result_with_secondary_keys(self):
        responses = [
            {"Users": ["User1", "User2"],
             "Groups": ["Group1", "Group2"],
             "Marker": "m1"},
            {"Users": ["User3"], "Groups": ["Group3"], "Marker": "m2"},
            {"Users": ["User4"], "Groups": ["Group4"]},
        ]
        self.method.side_effect = responses
        pages = self.paginator.paginate(
            PaginationConfig={'MaxItems': 1})
        complete = pages.build_full_result()
        self.assertEqual(complete,
                         {"Users": ["User1"], "Groups": ["Group1", "Group2"],
                          "NextToken": "None___1"})

    def test_resume_with_secondary_keys(self):
        # This is simulating a continutation of the previous test,
        # test_build_result_with_secondary_keys.  We use the
        # token specified in the response "None___1" to continue where we
        # left off.
        responses = [
            {"Users": ["User1", "User2"],
             "Groups": ["Group1", "Group2"],
             "Marker": "m1"},
            {"Users": ["User3"], "Groups": ["Group3"], "Marker": "m2"},
            {"Users": ["User4"], "Groups": ["Group4"]},
        ]
        self.method.side_effect = responses
        pages = self.paginator.paginate(
            PaginationConfig={'MaxItems': 1,
                              'StartingToken': "None___1"})
        complete = pages.build_full_result()
        # Note that the secondary keys ("Groups") are all truncated because
        # they were in the original (first) response.
        self.assertEqual(complete,
                         {"Users": ["User2"], "Groups": [],
                          "NextToken": "m1"})

    def test_resume_with_secondary_result_as_string(self):
        self.method.return_value = {"Users": ["User1", "User2"], "Groups": "a"}
        pages = self.paginator.paginate(
            PaginationConfig={'MaxItems': 1, 'StartingToken': "None___1"})
        complete = pages.build_full_result()
        # Note that the secondary keys ("Groups") becomes empty string because
        # they were in the original (first) response.
        self.assertEqual(complete, {"Users": ["User2"], "Groups": ""})

    def test_resume_with_secondary_result_as_integer(self):
        self.method.return_value = {"Users": ["User1", "User2"], "Groups": 123}
        pages = self.paginator.paginate(
            PaginationConfig={'MaxItems': 1, 'StartingToken': "None___1"})
        complete = pages.build_full_result()
        # Note that the secondary keys ("Groups") becomes zero because
        # they were in the original (first) response.
        self.assertEqual(complete, {"Users": ["User2"], "Groups": 0})


class TestMultipleInputKeys(unittest.TestCase):
    def setUp(self):
        self.method = mock.Mock()
        # Probably the most complicated example we'll see:
        # multiple input/output/result keys.
        self.paginate_config = {
            "output_token": ["Marker1", "Marker2"],
            "input_token": ["InMarker1", "InMarker2"],
            "result_key": ["Users", "Groups"],
        }
        self.paginator = Paginator(self.method, self.paginate_config)

    def test_build_full_result_with_multiple_input_keys(self):
        responses = [
            {"Users": ["User1", "User2"], "Groups": ["Group1"],
             "Marker1": "m1", "Marker2": "m2"},
            {"Users": ["User3", "User4"], "Groups": ["Group2"],
             "Marker1": "m3", "Marker2": "m4"},
            {"Users": ["User5"], "Groups": ["Group3"]}
        ]
        self.method.side_effect = responses
        pages = self.paginator.paginate(
            PaginationConfig={'MaxItems': 3})
        complete = pages.build_full_result()
        self.assertEqual(complete,
                         {"Users": ['User1', 'User2', 'User3'],
                          "Groups": ['Group1', 'Group2'],
                          "NextToken": "m1___m2___1"})

    def test_resume_with_multiple_input_keys(self):
        responses = [
            {"Users": ["User3", "User4"], "Groups": ["Group2"],
             "Marker1": "m3", "Marker2": "m4"},
            {"Users": ["User5"], "Groups": ["Group3"]},
        ]
        self.method.side_effect = responses
        pages = self.paginator.paginate(
            PaginationConfig={'MaxItems': 1,
                              'StartingToken': 'm1___m2___1'})
        complete = pages.build_full_result()
        self.assertEqual(complete,
                         {"Users": ['User4'],
                          "Groups": [],
                          "NextToken": "m3___m4"})
        self.assertEqual(
            self.method.call_args_list,
            [mock.call(InMarker1='m1', InMarker2='m2')])

    def test_resume_encounters_an_empty_payload(self):
        response = {"not_a_result_key": "it happens in some service"}
        self.method.return_value = response
        complete = self.paginator.paginate(
            PaginationConfig={'StartingToken': 'None___1'}).build_full_result()
        self.assertEqual(complete, {})

    def test_result_key_exposed_on_paginator(self):
        self.assertEqual(
            [rk.expression for rk in self.paginator.result_keys],
            ['Users', 'Groups']
        )

    def test_result_key_exposed_on_page_iterator(self):
        pages = self.paginator.paginate(MaxItems=3)
        self.assertEqual(
            [rk.expression for rk in pages.result_keys],
            ['Users', 'Groups']
        )


class TestExpressionKeyIterators(unittest.TestCase):
    def setUp(self):
        self.method = mock.Mock()
        # This is something like what we'd see in RDS.
        self.paginate_config = {
            "input_token": "Marker",
            "output_token": "Marker",
            "limit_key": "MaxRecords",
            "result_key": "EngineDefaults.Parameters"
        }
        self.paginator = Paginator(self.method, self.paginate_config)
        self.responses = [
            {"EngineDefaults": {"Parameters": ["One", "Two"]},
             "Marker": "m1"},
            {"EngineDefaults": {"Parameters": ["Three", "Four"]},
             "Marker": "m2"},
            {"EngineDefaults": {"Parameters": ["Five"]}}
        ]

    def test_result_key_iters(self):
        self.method.side_effect = self.responses
        pages = self.paginator.paginate()
        iterators = pages.result_key_iters()
        self.assertEqual(len(iterators), 1)
        self.assertEqual(list(iterators[0]),
                         ['One', 'Two', 'Three', 'Four', 'Five'])

    def test_build_full_result_with_single_key(self):
        self.method.side_effect = self.responses
        pages = self.paginator.paginate()
        complete = pages.build_full_result()
        self.assertEqual(complete, {
            'EngineDefaults': {
                'Parameters': ['One', 'Two', 'Three', 'Four', 'Five']
            },
        })


class TestIncludeResultKeys(unittest.TestCase):
    def setUp(self):
        self.method = mock.Mock()
        self.paginate_config = {
            'output_token': 'Marker',
            'input_token': 'Marker',
            'result_key': ['ResultKey', 'Count', 'Log'],
        }
        self.paginator = Paginator(self.method, self.paginate_config)

    def test_different_kinds_of_result_key(self):
        self.method.side_effect = [
            {'ResultKey': ['a'], 'Count': 1, 'Log': 'x', 'Marker': 'a'},
            {'not_a_result_key': 'this page will be ignored', 'Marker': '_'},
            {'ResultKey': ['b', 'c'], 'Count': 2, 'Log': 'y', 'Marker': 'b'},
            {'ResultKey': ['d', 'e', 'f'], 'Count': 3, 'Log': 'z'},
        ]
        pages = self.paginator.paginate()
        expected = {
            'ResultKey': ['a', 'b', 'c', 'd', 'e', 'f'],
            'Count': 6,
            'Log': 'xyz',
        }
        self.assertEqual(pages.build_full_result(), expected)

    def test_result_key_is_missing(self):
        self.method.side_effect = [
            {'not_a_result_key': 'this page will be ignored', 'Marker': '_'},
            {'neither_this_one': 'this page will be ignored, too'},
        ]
        pages = self.paginator.paginate()
        expected = {}
        self.assertEqual(pages.build_full_result(), expected)


class TestIncludeNonResultKeys(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.method = mock.Mock()
        self.paginate_config = {
            'output_token': 'NextToken',
            'input_token': 'NextToken',
            'result_key': 'ResultKey',
            'non_aggregate_keys': ['NotResultKey'],
        }
        self.paginator = Paginator(self.method, self.paginate_config)

    def test_include_non_aggregate_keys(self):
        self.method.side_effect = [
            {'ResultKey': ['foo'], 'NotResultKey': 'a', 'NextToken': 't1'},
            {'ResultKey': ['bar'], 'NotResultKey': 'a', 'NextToken': 't2'},
            {'ResultKey': ['baz'], 'NotResultKey': 'a'},
        ]
        pages = self.paginator.paginate()
        actual = pages.build_full_result()
        self.assertEqual(pages.non_aggregate_part, {'NotResultKey': 'a'})
        expected = {
            'ResultKey': ['foo', 'bar', 'baz'],
            'NotResultKey': 'a',
        }
        self.assertEqual(actual, expected)

    def test_include_with_multiple_result_keys(self):
        self.paginate_config['result_key'] = ['ResultKey1', 'ResultKey2']
        self.paginator = Paginator(self.method, self.paginate_config)
        self.method.side_effect = [
            {'ResultKey1': ['a', 'b'], 'ResultKey2': ['u', 'v'],
             'NotResultKey': 'a', 'NextToken': 'token1'},
            {'ResultKey1': ['c', 'd'], 'ResultKey2': ['w', 'x'],
             'NotResultKey': 'a', 'NextToken': 'token2'},
            {'ResultKey1': ['e', 'f'], 'ResultKey2': ['y', 'z'],
             'NotResultKey': 'a'}
        ]
        pages = self.paginator.paginate()
        actual = pages.build_full_result()
        expected = {
            'ResultKey1': ['a', 'b', 'c', 'd', 'e', 'f'],
            'ResultKey2': ['u', 'v', 'w', 'x', 'y', 'z'],
            'NotResultKey': 'a',
        }
        self.assertEqual(actual, expected)

    def test_include_with_nested_result_keys(self):
        self.paginate_config['result_key'] = 'Result.Key'
        self.paginate_config['non_aggregate_keys'] = [
            'Outer', 'Result.Inner',
        ]
        self.paginator = Paginator(self.method, self.paginate_config)
        self.method.side_effect = [
            # The non result keys shows hypothetical
            # example.  This doesn't actually happen,
            # but in the case where the non result keys
            # are different across pages, we use the values
            # from the first page.
            {'Result': {'Key': ['foo'], 'Inner': 'v1'},
             'Outer': 'v2', 'NextToken': 't1'},
            {'Result': {'Key': ['bar', 'baz'], 'Inner': 'v3'},
             'Outer': 'v4', 'NextToken': 't2'},
            {'Result': {'Key': ['qux'], 'Inner': 'v5'},
             'Outer': 'v6', 'NextToken': 't3'},
        ]
        pages = self.paginator.paginate()
        actual = pages.build_full_result()
        self.assertEqual(pages.non_aggregate_part,
                         {'Outer': 'v2', 'Result': {'Inner': 'v1'}})
        expected = {
            'Result': {'Key': ['foo', 'bar', 'baz', 'qux'], 'Inner': 'v1'},
            'Outer': 'v2',
        }
        self.assertEqual(actual, expected)


class TestSearchOverResults(unittest.TestCase):
    def setUp(self):
        self.method = mock.Mock()
        self.paginate_config = {
            'more_results': 'IsTruncated',
            'output_token': 'NextToken',
            'input_token': 'NextToken',
            'result_key': 'Foo',
        }
        self.paginator = Paginator(self.method, self.paginate_config)
        responses = [
            {'Foo': [{'a': 1}, {'b': 2}],
             'IsTruncated': True, 'NextToken': '1'},
            {'Foo': [{'a': 3}, {'b': 4}],
             'IsTruncated': True, 'NextToken': '2'},
            {'Foo': [{'a': 5}], 'IsTruncated': False, 'NextToken': '3'}
        ]
        self.method.side_effect = responses

    def test_yields_non_list_values(self):
        result = list(self.paginator.paginate().search('Foo[0].a'))
        self.assertEqual([1, 3, 5], result)

    def test_yields_individual_list_values(self):
        result = list(self.paginator.paginate().search('Foo[].*[]'))
        self.assertEqual([1, 2, 3, 4, 5], result)

    def test_empty_when_no_match(self):
        result = list(self.paginator.paginate().search('Foo[].qux'))
        self.assertEqual([], result)

    def test_no_yield_when_no_match_on_page(self):
        result = list(self.paginator.paginate().search('Foo[].b'))
        self.assertEqual([2, 4], result)


if __name__ == '__main__':
    unittest.main()
