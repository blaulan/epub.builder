#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Eric Wu
# @Date:   2013-11-27 23:46:41
# @Email:  me@blaulan.com
# @Last modified by:   Eric Wu
# @Last Modified time: 2013-11-30 21:05:25

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

config = {
    'description': 'Epub Builder',
    'author': 'Eric Wu',
    'url': 'https://github.com/blaulan/Python-Epub-Builder',
    'download_url': 'https://github.com/blaulan/Python-Epub-Builder',
    'author_email': 'me@blaulan.com',
    'version': '0.1',
    'install_requires': ['nose', 'genshi', 'lxml'],
    'packages': ['epub'],
    'scripts': [],
    'name': 'Epub Builder'
}

setup(**config)