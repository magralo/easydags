from distutils.core import setup
setup(
  name = 'easydags',         # How you named your package folder (MyLib)
  packages = ['easydags'],   # Chose the same as "name"
  version = '0.0.2',      # Start with a small number and increase it with every change you make
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
  classifiers=[
    'Development Status :: 3 - Alpha',      
  ],
)