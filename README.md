# ![logo](https://github.com/robertfmath/Create-Intro-Cards/blob/main/docs/source/_static/images/logo.svg?raw=true)

<div align="center">

[![CI Status](https://github.com/robertfmath/Create-Intro-Cards/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/robertfmath/Create-Intro-Cards/actions/workflows/ci.yml)
[![PyPI Latest Release](https://img.shields.io/pypi/v/create-intro-cards.svg)](https://pypi.org/project/create-intro-cards/)
[![License](https://img.shields.io/badge/License-BSD_3--Clause-yellow.svg)](https://github.com/robertfmath/Create-Intro-Cards/blob/main/LICENSE.txt)
[![Documentation](https://img.shields.io/badge/Documentation-gray)](https://robertfmath.github.io/Create-Intro-Cards)

</div>

`create-intro-cards` is a Python module that transforms a data set of individuals' names, photos, and custom attributes into a paginated PDF consisting of "intro cards" that describe each individual. Each intro card displays a person's name, their photo, and a series of attributes based on custom columns in the data set.

<p align="center">
  <img src="https://github.com/robertfmath/Create-Intro-Cards/blob/main/docs/source/_static/images/example_output_page.png?raw=true" alt="An example of one page of output in the pdf" style="height: 500px; width: auto; object-fit: contain;">
</p>

The input to the main function — `make_pdf` — is a Pandas DataFrame, where rows represent individuals and columns their attributes. Columns containing individuals' first names, last names, and paths to their photos are required, but the content (and number) of other columns is arbitrary and completely up to the user.

<p align="center">
  <img src="https://github.com/robertfmath/Create-Intro-Cards/blob/main/docs/source/_static/images/example_people_data.png?raw=true" alt="An example of the structure of the input Pandas DataFrame" style="height: 150; width: auto; object-fit: contain;">
</p>

These arbitrary columns are used to generate a series of "column name: attribute value" pairings (e.g., "Hometown: New York, NY") for each individual, which is then plotted below their name on their intro card. If an individual doesn't have a value listed for any arbitrary column, that column's "column name: attribute value" pairing will be omitted from their card.

The shareable output PDF contains all individuals' intro cards, four per page. It's a great way for people to get to know each other!

## Dependencies

- NumPy
- Pandas
- Matplotlib
- Pillow
- ipykernel

For a full list of dependencies&mdash;both direct and transitive&mdash;please refer to the provided `requirements.txt` file. The `requirements-dev.txt` file provides additional dependencies for development — namely Black, docformatter, Sphinx, and pypdf.

## Installation

With Python installed, simply run:

```bash
pip install create-intro-cards
```

## Usage

The entrypoint of the module is the function `make_pdf`, which generates a PDF containing intro cards for all the individuals in the input Pandas DataFrame. The function is passed this DataFrame; the names of the columns in the DataFrame that house first names, last names, and paths to individuals' photos; a path to a default photo to use in the event an individual doesn't have a photo path listed; and a path to the directory in which to store the output.

```python
from create_intro_cards import make_pdf
import pandas as pd

people_data = pd.read_csv('path/to/people/data.csv')

make_pdf(people_data, 'First Name', 'Last Name', 'Photo Path', 'path/to/default/photo.png', 'path/to/output/dir')
```

The output directory will contain the PDF, PNG images of all the PDF's constituent pages, and a logging file that denotes the names and photo availability statuses of all the individuals who had an intro card created.

`make_pdf` also provides optional keyword arguments to tweak the default layout of the intro cards, from font sizes and text placement to photo boundaries and more.

```python
make_pdf(people_data, 'First Name', 'Last Name', 'Photo Path', 'path/to/default/photo.png', 'path/to/output/dir',
         figure_size=(20, 10), name_x_coord=0.40, desc_font_size=14, photo_axes_bounds=(0.01, 0.02, 0.2, 0.92))
```

To see how the different keyword arguments affect the appearance of the intro cards, a utility function called `make_pdf_preview` is provided. This function, which must be run in a Jupyter environment, displays a mock-up of the first page of the PDF that would otherwise be created if `make_pdf` were run with the same arguments (minus `path_to_output_dir`). Since it doesn't iterate through the entire data set, it takes a fraction of the time that `make_pdf` does and is ideal for prototyping.

```python
make_pdf_preview(people_data, 'First Name', 'Last Name', 'Photo Path', 'path/to/default/photo.png', 
                 figure_size=(20, 10), name_x_coord=0.40, desc_font_size=14, photo_axes_bounds=(0.01, 0.02, 0.2, 0.92))
```

## Documentation

For full documentation, please see [here](https://robertfmath.github.io/Create-Intro-Cards).
