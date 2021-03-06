#!/usr/bin/env python

from setuptools import setup

setup_requires = ['nose>=1.0']

with open("../README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='reticul8',
    version='0.1',
    packages=['reticul8'],
    url='https://github.com/xlfe/reticul8',
    license='GNU General Public License v3.0',
    author='xlfe',
    description='Remotely articulated MCU endpoints for Python',
    long_description=long_description,
    long_description_content_type="text/markdown",
    setup_requires=setup_requires,
    test_suite = 'nose.collector',
    classifiers = [
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
    ]
)
