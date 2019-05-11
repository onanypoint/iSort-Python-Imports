# iSort Sublime-Text Package

Sublime Text 3 package to run the [isort](https://github.com/timothycrosley/isort) Python import formatter.

## Usage

Select "iSort: Format Document" to run ```isort``` on the current document. To run iSort on the current document before saving, use the ```on_save``` setting.

## Installation

* Install iSort (if you haven't already):

        pip install isort

* Install Sublime Package Control by following the instructions here (if you haven't already).

    * ```Ctrl-Shift-P``` (Mac: Cmd-Shift-P) and choose "Package Control: Install Package".
    *  Find "iSort Python Imports" in the list (type in a few characters and you should see it).

* Update the ```isort_command``` setting with the path to your installation of ```isort```. You can learn the exact path using ```which isort```.

Alternatively, install manually by navigating to Sublime's Packages folder and cloning this repository:

    git clone https://github.com/onanypoint/iSort-Python-Imports "iSort Python Imports"

## Acknowledgement

This repository is heavily inspired by [PyYapf Python Formatter](https://github.com/jason-kane/PyYapf). If you haven't installed their package yet, do it!

## LICENSE

Apache v2 per LICENSE. Do what you want; if you fix something please share it. Pull requests welcome.
