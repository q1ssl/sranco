from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in sranco/__init__.py
from sranco import __version__ as version

setup(
	name="sranco",
	version=version,
	description="customizations",
	author="Amit Kumar",
	author_email="amit@worf.in",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
