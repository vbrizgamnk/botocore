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
from tests.functional.docs import BaseDocsFunctionalTest
from botocore.docs.service import ServiceDocumenter


class TestCloudFormationDocs(BaseDocsFunctionalTest):
    def test_get_template_response_documented_as_dict(self):
        content = self.get_docstring_for_method('cloudformation', 'get_template')
        # Should not say the return type of template body is a string
        self.assert_not_contains_line(
            "TemplateBody: string", content)
        # Check for template body returning a dict
        self.assert_contains_line(
            "TemplateBody: dict", content)
        # Check the specifics of the returned dict
        self.assert_contains_line('{}', content)
