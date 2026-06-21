from setuptools import setup

package_name = "amr_safety"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Anzal Ahmed",
    maintainer_email="anzal.ahmed2001@gmail.com",
    description="Watchdog, e-stop manager, and workspace geo-fence for AMR fleet",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "watchdog = amr_safety.watchdog_node:main",
        ],
    },
)
