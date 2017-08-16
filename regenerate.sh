#! /bin/sh

rm -rf db
mkdir db
for i in 2016-09-26.json 2016-11-04.json 2017-08-16.json; do
   ./nodes2eventlog.py ../nodes-json-old/$i db foo.atom
done
./graveyard2rst.py db graveyard.rst; cat graveyard.rst
