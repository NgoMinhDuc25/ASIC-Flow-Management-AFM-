from setuptools import setup, find_packages

setup(
    name="afm",
    version="0.2.2",
    description="ASIC Flow Management (AFM) - lightweight folder/version control system for ASIC Physical Design flows",
    author="ducnm153",
    packages=find_packages(include=["afm*"]),
    python_requires=">=3.6",
    install_requires=[
        "PyYAML>=5.1",
        "PyQt5>=5.15.0",
        "dataclasses; python_version < '3.7'"
    ],
    entry_points={
        "console_scripts": [
            "afm=afm.cli:main"
        ]
    }
)



