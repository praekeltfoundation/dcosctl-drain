from setuptools import find_packages, setup

setup(
    name="dcosctl_drain",
    version="0.1.0.dev0",
    description=("Python script for easier interaction with Mesos maintenance "
                 "primitives"),
    author="Jamie Hewland",
    author_email="sre@praekelt.org",
    packages=find_packages(),
    install_requires=["requests"],
    extras_require={
        "lint": ["flake8"]
    },
    entry_points={
        "console_scripts": ["dcosctl=dcosctl:main"],
    }
)
