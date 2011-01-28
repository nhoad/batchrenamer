#!/bin/bash
cd /home/nathan/projects/deluge-plugin/new/batchrenamer
mkdir temp
export PYTHONPATH=./temp
python2 setup.py build develop --install-dir ./temp
cp ./temp/BatchRenamer.egg-link /home/nathan/.config/deluge/plugins
rm -fr ./temp
