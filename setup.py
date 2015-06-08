#!/usr/bin/env python
import sys
import botocore

from setuptools import setup, find_packages


requires = ['jmespath==0.7.1',
            'bcdoc>=0.15.0,<0.16.0',
            'python-dateutil>=2.1,<3.0.0']


setup(
    name='botocore',
    version=botocore.__version__,
    description='Low-level, data-driven core of boto 3.',
    long_description=open('README.rst').read(),
    author='Mitch Garnaat',
    author_email='garnaat@amazon.com',
    url='https://github.com/boto/botocore',
    scripts=[],
    packages=find_packages(exclude=['tests*']),
    package_data={'botocore': ['data/*.json', 'data/aws/*.json'],
                  'botocore.vendored.requests': ['*.pem']},
    package_dir={'botocore': 'botocore'},
    include_package_data=True,
    install_requires=requires,
    extras_require={
        ':python_version=="2.6"': [
            'ordereddict==1.1',
            'simplejson==3.3.0',
        ]
    },
    license=open("LICENSE.txt").read(),
    classifiers=(
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Natural Language :: English',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
    ),
)
