#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup
from app_version import APP_VERSION, REPOSITORY_URL

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
    'PyQt5>=5.15,<6',
    'rasterio>=1.3,<2',
    'numpy>=1.24',
    'lxml>=4.9',
]

test_requirements = [
    'qt',
    'qt4',
    'libxml2'
]

setup(
    name='labelImg',
    version=APP_VERSION,
    description="LabelImg is a graphical image annotation tool and label object bounding boxes in images",
    long_description=readme + '\n\n' + history,
    author="TzuTa Lin",
    author_email='tzu.ta.lin@gmail.com',
    url=REPOSITORY_URL,
    packages=[
        'labelImg', 'labelImg.libs'
    ],
    package_dir={'labelImg': '.'},
    entry_points={
        'console_scripts': [
            'labelImg=labelImg.roLabelImg:main'
        ]
    },
    include_package_data=True,
    install_requires=requirements,
    license="MIT license",
    zip_safe=False,
    keywords='labelImg',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    test_suite='tests',
    tests_require=test_requirements
)
