#!/usr/bin/env python3
"""Setup script for hecat"""
import codecs
import os
import re

from setuptools import find_packages, setup

setup(
    name='hecat',
    version='0.0.1',
    description='Software catalog generator',
    long_description='Software catalog generator',
    author='nodiscc',
    maintainer='nodiscc',
    maintainer_email='nodiscc@gmail.com',
    license='GPL-3.0',
    url='https://gitlab.com/nodiscc/hecat',
    keywords='yaml generator alternative software list',
    packages=find_packages(exclude=['tests.*', 'tests']),
    entry_points={
        'console_scripts': [
            'hecat = hecat.main:main',
        ],
    },
    install_requires=[
        'ruamel.yaml',
        'PyGithub'
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GPL-3.0 License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Topic :: Utilities',
    ]
)
