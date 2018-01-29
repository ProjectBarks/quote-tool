from setuptools import setup, find_packages
from distutils.core import setup
from Cython.Build import cythonize
import numpy

setup(
    name='coinbase-quote',
    version='1.0.0',
    author='Brandon Barker',
    author_email='contact@brandonbarker.me',
    description='A simple coinbase quote tool using a knapsack algorithm and cython',
    packages=find_packages(),
    ext_modules=cythonize('knapsack.pyx'),
    include_dirs=[numpy.get_include()],
    install_requires=[
        'sanic==0.7.0',
        'numpy==1.14.0',
        'cython==0.27.3',
        'websocket-client==0.46.0',
        'bintrees==2.0.7',
        'requests==2.18.4'
    ]
)
