#!/bin/sh

# This script automates the process of formatting the Python code (using Black), 
# formatting docstrings (using docformatter), running tests, and locally building the project's  
# documentation (using Sphinx). The GitHub Actions workflow expects formatting to have already been applied
# and tests to have passed, so this is useful to run before pushing or creating a pull request. 

# Run Black on create_intro_cards.py and test_create_intro_cards.py
echo "Running Black on create_intro_cards.py"
black create_intro_cards.py
echo "Running Black on tests/test_create_intro_cards.py"
black tests/test_create_intro_cards.py

if [ $? -ne 0 ]; then
    echo "Black formatting failed."
    exit 1
fi

# Run docformatter to format docstrings in accordance with Black 
# Options specified in pyproject.toml
echo "Running docformatter on create_intro_cards.py"
docformatter create_intro_cards.py
echo "Running docformatter on tests/test_create_intro_cards.py"
docformatter tests/test_create_intro_cards.py

if [ $? -ne 0 ]; then
    echo "Docformatter failed."
    exit 1
fi

# Run tests
echo "Running tests"
python -m unittest tests/test_create_intro_cards.py
if [ $? -ne 0 ]; then
    echo "Tests failed."
    exit 1
fi

# Build documentation with Sphinx
cd ./docs

echo "Building documentation with Sphinx"
if [ "$(uname)" = "Darwin" ] || [ "$(uname)" = "Linux" ]; then
    make clean && make html
else
    ./make.bat clean && ./make.bat html
fi

if [ $? -ne 0 ]; then
    echo "Documentation build failed."
    exit 1
fi

cd ..

exit 0
