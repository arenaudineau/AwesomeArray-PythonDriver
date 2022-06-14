from setuptools import setup, find_packages

setup(
	name='AwesomeArray-Driver',
	version='0.0.1',
	packages=['aad'],
	install_requires=[
		'pyserial',
		'pyvisa'
	]
)