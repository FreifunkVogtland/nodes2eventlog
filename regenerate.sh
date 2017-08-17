#! /bin/sh

rm -rf db
mkdir db
for i in \
2016-06-14.json \
2016-07-04.json \
2016-08-05.json \
2016-09-06.json \
2016-09-26.json \
2016-11-04.json \
2016-12-04.json \
2017-04-25.json \
2017-07-18.json \
2017-08-16.json \
; do
   ./nodes2eventlog.py ../nodes-json-old/$i db foo.atom
done
./nodes2eventlog.py ../nodes-json-old/$i db final.atom
./nodes2eventlog.py ../nodes-json-old/2017-08-16.json db foo.atom
./graveyard2rst.py db graveyard.rst; cat graveyard.rst
