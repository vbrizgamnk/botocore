#!/usr/bin/env python
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

from tests import TestParamSerialization
import base64
import six
import botocore.session


class TestEC2Operations(TestParamSerialization):
    maxDiff = None

    def setUp(self):
        super(TestEC2Operations, self).setUp()
        self.ec2 = self.session.get_service('ec2')

    def test_describe_instances_no_params(self):
        self.assert_params_serialize_to('ec2.DescribeInstances', {}, {})

    def test_describe_instances_instance_id(self):
        params = dict(instance_ids=['i-12345678'])
        result = {'InstanceId.1': 'i-12345678'}
        self.assert_params_serialize_to('ec2.DescribeInstances', params, result)

    def test_describe_instances_instance_ids(self):
        params = dict(instance_ids=['i-12345678', 'i-87654321'])
        result = {'InstanceId.1': 'i-12345678', 'InstanceId.2': 'i-87654321'}
        self.assert_params_serialize_to('ec2.DescribeInstances', params, result)

    def test_describe_instances_filter(self):
        params = dict(filters=[{'Name': 'group-name', 'Values': ['foobar']}])
        result = {'Filter.1.Value.1': 'foobar', 'Filter.1.Name': 'group-name'}
        self.assert_params_serialize_to('ec2.DescribeInstances', params, result)

    def test_describe_instances_filter_values(self):
        params = dict(filters=[{'Name': 'group-name', 'Values': ['foobar', 'fiebaz']}])
        result = {'Filter.1.Value.2': 'fiebaz',
                  'Filter.1.Value.1': 'foobar',
                  'Filter.1.Name': 'group-name'}
        self.assert_params_serialize_to('ec2.DescribeInstances', params, result)

    def test_create_tags(self):
        params = dict(resources=['i-12345678', 'i-87654321'],
                      tags=[{'Key': 'key1', 'Value': 'value1'},
                            {'Key': 'key2', 'Value': 'value2'}])
        result = {'ResourceId.1': 'i-12345678',
                  'ResourceId.2': 'i-87654321',
                  'Tag.1.Key': 'key1', 'Tag.1.Value': 'value1',
                  'Tag.2.Key': 'key2', 'Tag.2.Value': 'value2'}
        self.assert_params_serialize_to('ec2.CreateTags', params, result)

    def test_request_spot_instances(self):
        op = self.ec2.get_operation('RequestSpotInstances')
        params = dict(spot_price='1.00', instance_count=1,
                      launch_specification={
                          'ImageId': 'ami-33ec795a',
                          'InstanceType': 'cc2.8xlarge',
                          'BlockDeviceMappings': [
                              {"DeviceName": "/dev/sdb", "VirtualName": "ephemeral0"},
                              {"DeviceName": "/dev/sdc", "VirtualName": "ephemeral1"},
                              {"DeviceName": "/dev/sdd", "VirtualName": "ephemeral2"},
                              {"DeviceName": "/dev/sde", "VirtualName": "ephemeral3"}]})
        result = {'SpotPrice': '1.00',
                  'InstanceCount': 1,
                  'LaunchSpecification.ImageId': 'ami-33ec795a',
                  'LaunchSpecification.InstanceType': 'cc2.8xlarge',
                  'LaunchSpecification.BlockDeviceMapping.1.DeviceName': '/dev/sdb',
                  'LaunchSpecification.BlockDeviceMapping.2.DeviceName': '/dev/sdc',
                  'LaunchSpecification.BlockDeviceMapping.3.DeviceName': '/dev/sdd',
                  'LaunchSpecification.BlockDeviceMapping.4.DeviceName': '/dev/sde',
                  'LaunchSpecification.BlockDeviceMapping.1.VirtualName': 'ephemeral0',
                  'LaunchSpecification.BlockDeviceMapping.2.VirtualName': 'ephemeral1',
                  'LaunchSpecification.BlockDeviceMapping.3.VirtualName': 'ephemeral2',
                  'LaunchSpecification.BlockDeviceMapping.4.VirtualName': 'ephemeral3'}
        self.assert_params_serialize_to('ec2.RequestSpotInstances', params, result)

    def test_run_instances_userdata(self):
        user_data = 'This is a test'
        b64_user_data = base64.b64encode(six.b(user_data)).decode('utf-8')
        op = self.ec2.get_operation('RunInstances')
        params = dict(image_id='img-12345678',
                      min_count=1, max_count=5, user_data=user_data)
        result = {'ImageId': 'img-12345678',
                  'MinCount': 1,
                  'MaxCount': 5,
                  'UserData': b64_user_data}
        # TODO: We need to base64 decode this!  Needs a customization
        #self.assert_params_serialize_to('ec2.RunInstances', params, result)

    def test_authorize_security_groups_ingress(self):
        params = dict(
            group_name='MyGroup',
            ip_permissions=[{
                'FromPort': 22, 'ToPort': 22,
                'IpProtocol': 'tcp',
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}])
        result = {'GroupName': 'MyGroup',
                  'IpPermissions.1.FromPort': 22,
                  'IpPermissions.1.ToPort': 22,
                  'IpPermissions.1.IpProtocol': 'tcp',
                  'IpPermissions.1.IpRanges.1.CidrIp': '0.0.0.0/0',}
        self.assert_params_serialize_to('ec2.AuthorizeSecurityGroupIngress', params, result)

    def test_modify_volume_attribute(self):
        params = dict(
            volume_id='vol-12345678',
            auto_enable_io={'Value': True})

        result = {'VolumeId': 'vol-12345678',
                  'AutoEnableIO.Value': 'true'}

        self.assert_params_serialize_to('ec2.ModifyVolumeAttribute', params, result)
