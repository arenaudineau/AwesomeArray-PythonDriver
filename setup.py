from setuptools import setup, find_packages

setup(
	name='AwesomeArray-Driver',
	version='0.0.1',
	packages=find_packages(),
	install_requires=[
		'pyserial',
		'B1530Lib @ https://github.com/arenaudineau/B1530Lib/archive/refs/heads/main.zip'
	]
)