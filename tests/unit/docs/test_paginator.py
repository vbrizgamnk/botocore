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
from tests.unit.docs import BaseDocsTest
from botocore.docs.paginator import PaginatorDocumentor
from botocore.paginate import PaginatorModel


class TestPaginatorDocumentor(BaseDocsTest):
    def setUp(self):
        super(TestPaginatorDocumentor, self).setUp()
        self.add_shape_to_params('Biz', 'String')
        self.extra_setup()

    def extra_setup(self):
        self.setup_client()
        paginator_model = PaginatorModel(self.paginator_json_model)
        self.paginator_documentor = PaginatorDocumentor(
            client=self.client, service_paginator_model=paginator_model)

    def test_document_paginators(self):
        self.paginator_documentor.document_paginators(
            self.doc_structure)
        self.assert_contains_lines([
            '==========',
            'Paginators',
            '==========',
            'The available paginators are:',
            '* :py:class:`myservice.Paginator.sample_operation`',
            '.. py:class:: myservice.Paginator.sample_operation',
            '  ::',
            '    paginator = client.get_paginator(\'sample_operation\')',
            ('  .. py:method:: paginate(Biz=None, max_items=None, '
             'page_size=None, starting_token=None)'),
            ('    Creates an iterator that will paginate through responses'
             ' from :py:meth:`myservice.Client.sample_operation`.'),
            '    **Example**',
            '    ::',
            '      response_iterator = paginator.paginate(',
            '          Biz=\'string\',',
            '          max_items=123,',
            '          page_size=123,',
            '          starting_token=\'string\'',
            '      )',
            '    :type Biz: string',
            '    :param Biz:',
            '    :type max_items: integer',
            '    :param max_items:',
            '    :type page_size: integer',
            '    :param page_size:',
            '    :type starting_token: string',
            '    :param starting_token:',
            '    :rtype: dict',
            '    :returns:',
            '      **Response Example**',
            '      ::',
            '        {',
            '            \'Biz\': \'string\',',
            '            \'NextToken\': \'string\'',
            '        }',
            '      **Response Structure**',
            '      - *(dict) --*',
            '        - **Biz** *(string) --*',
            '        - **NextToken** *(string) --*'
        ])
