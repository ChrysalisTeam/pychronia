#!/usr/bin/env python
# -*- coding: utf8 -*-

from setuptools import setup, find_packages

setup(
    name='cmsplugin-simple-gallery',
    version='0.0.1.1',
    description='Simple django cms gallery plugin.',
    author='Denys Chmeliuk',
    author_email='d.chmeluyk@gmail.com',
    url='http://github.com/chmeliuk/cmsplugin-simple-gallery/',
    packages=find_packages(),
    provides=['cmsplugin_simple_gallery',],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Django',
        ],
    include_package_data=True,
    zip_safe=False,
    install_requires = ['django-inline-ordering>=0.1.1', 'easy-thumbnails',]
)
