from setuptools import setup

with open("README.md", "r") as fp:
    long_description = fp.read()

with open('VERSION', 'r') as fp:
    version = fp.read()

setup(name="catan-spectator",
      version=version,
      author="Ross Anderson",
      author_email="ross.anderson@ualberta.ca",
      url="https://github.com/rosshamish/catan-spectator/",
      download_url = 'https://github.com/rosshamish/catan-spectator/tarball/'+version,
      description='Transcribe games of Settlers of Catan for research purposes, replay purposes, broadcast purposes, etc.',
      long_description=long_description,
      keywords=[],
      classifiers=[],
      license="GPLv3",

      entry_points={
          'gui_scripts': [
              'catan-spectator = main:main'
          ]
      },
      py_modules=[
          'main',
          'views',
          'views_trading',
          'tkinterutils',
      ],
      install_requires=[
          'catan ~= 0.4',
          'catanlog ~= 0.10',
          'hexgrid ~= 0.2',
          'undoredo ~= 0.1',
      ],
      )