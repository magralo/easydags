from distutils.core import setup

# read the contents of your README file
from pathlib import Path
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()


setup(
  name = 'easydags',         # How you named your package folder (MyLib)
  packages = ['easydags'],   # Chose the same as "name"
  version = '0.1.1',      # Start with a small number and increase it with every change you make
  description = 'Dags made easy',   # Give a short description about your library
  author = 'Mateo Graciano',                   # Type in your name
  author_email = 'magralo@gmail.com',      # Type in your E-Mail
  install_requires=[            # I get to this in a second
          'networkx==2.6.3',
          'pydantic==1.10',
          'loguru==0.6.0',
          'matplotlib==3.6.3',
          'pyvis==0.3.1'
      ],
  long_description=long_description,
  long_description_content_type='text/markdown',
)