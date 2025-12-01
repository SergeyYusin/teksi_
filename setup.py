# setup.py
from setuptools import setup, find_packages

setup(
    name="flask-site",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        'Flask>=2.3.0',
        'python-dotenv>=1.0.0',
    ],
)