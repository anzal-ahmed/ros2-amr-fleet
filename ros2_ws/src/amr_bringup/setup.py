import os
from glob import glob
from setuptools import setup

package_name = "amr_bringup"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", glob("launch/*.py")),
        (f"share/{package_name}/config", glob("config/*")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Anzal Ahmed",
    maintainer_email="anzal.ahmed2001@gmail.com",
    description="Launch files and configuration for the AMR fleet system",
    license="Apache-2.0",
    entry_points={"console_scripts": []},
)
