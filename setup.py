#!/usr/bin/env python
"""Setup for py_eiscp module."""
from setuptools import setup


def readme():
    """Return README file as a string."""
    with open("README.rst", "r") as f:
        return f.read()


setup(
    name="pyeiscp",
    version="0.0.7",
    author="Mathieu Pasquet",
    author_email="mat@pyeiscp.pasquet.co",
    url="https://github.com/winterscar/python-eiscp",
    license="LICENSE",
    packages=["pyeiscp"],
    scripts=[],
    description="Python API for controlling Anthem Receivers",
    long_description=readme(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    include_package_data=True,
    install_requires=[
        "netifaces",
    ],
    zip_safe=True,
    entry_points={"console_scripts": ["eiscp_monitor = pyeiscp.tools:monitor","eiscp_sender = pyeiscp.tools:sender",]},
)
