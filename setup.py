from setuptools import setup, find_packages

# read the contents of your README file
from pathlib import Path
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()


setup(
  name = 'easydags',
  packages = find_packages(exclude=['tests', 'tests.*']),
  version = '1.1.0',
  description = 'Dags made easy',
  author = 'Mateo Graciano',
  author_email = 'magralo@gmail.com',
  python_requires = '>=3.9',
  install_requires=[
          'networkx>=3.0',
          'pydantic>=2.0',
          'pydantic-settings>=2.0',
          'loguru>=0.7.0',
          'matplotlib>=3.8.0',
          'pyvis>=0.3.2'
      ],
  long_description=long_description,
  long_description_content_type='text/markdown',
  classifiers=[
      'Programming Language :: Python :: 3',
      'Programming Language :: Python :: 3.9',
      'Programming Language :: Python :: 3.10',
      'Programming Language :: Python :: 3.11',
      'Programming Language :: Python :: 3.12',
      'Programming Language :: Python :: 3.13',
      'License :: OSI Approved :: MIT License',
      'Operating System :: OS Independent',
  ],
)