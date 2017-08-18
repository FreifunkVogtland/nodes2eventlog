#!/usr/bin/python3
# -*- coding: utf-8; -*-

import sys
import os
import os.path
import pickle
import pprint
import datetime

def load_state(path):
	try:
		return pickle.load(open(path, 'rb'))
	except FileNotFoundError:
		return dict()


def usage():
	prog = 'graveyard2rst.py'
	if len(sys.argv) > 0:
		prog = sys.argv[0]

	print('%s DBPATH OUT_RST' % (prog))

def graveyard2zones(graveyard):
	zones = {}
	old_node_timelimit = datetime.datetime.utcnow() - datetime.timedelta(14)

	for node_id in graveyard:
		node = graveyard[node_id]
		node['id'] = node_id

		if old_node_timelimit < node['lastseen']:
			continue

		year = node['lastseen'].year
		if not year in zones:
			zones[year] = {}

		month = node['lastseen'].month
		if not month in zones[year]:
			zones[year][month] = []

		zones[year][month].append(node)

	for year in zones:
		for month in zones[year]:
			zones[year][month].sort(reverse = True, key = lambda node: (node['lastseen'].date(), node['firstseen'].date()))

	return zones

def write_zones(f, zones):
	years = list(zones.keys())
	years.sort(reverse = True)

	f.write("=========\n")
	f.write("Graveyard\n")
	f.write("=========\n")

	for year in years:
		f.write("\n%u\n" % year)
		f.write("%s\n" % ("=" * len(str(year))))

		months = list(zones[year].keys())
		months.sort(reverse = True)

		for month in months:
			title = "%u-%02u" % (year, month)
			f.write("\n%s\n" % (title))
			f.write("%s\n\n" % ("-" * len(title)))

			for node in zones[year][month]:
				f.write("* %s\n" % node['hostname'])
				f.write("  - id: %s\n" % node['id'])
				born = node['firstseen'].strftime('%Y-%m-%d')
				died = node['lastseen'].strftime('%Y-%m-%d')
				f.write("  - lifespan: %s - %s\n" % (born, died))
				f.write("\n")


	pass

def main():
	if len(sys.argv) != 3:
		usage()
		sys.exit(1)

	dbpath = sys.argv[1]
	feed_out = sys.argv[2]

	graveyard_path = os.path.join(dbpath, "graveyard.pickle")
	feed_outtmp = feed_out + '.tmp'

	# load
	graveyard = load_state(graveyard_path)

	# data crunching
	zones = graveyard2zones(graveyard)

	# save
	with open(feed_outtmp, 'w') as f:
		write_zones(f, zones)
		f.flush()
		os.fsync(f.fileno())

	os.rename(feed_outtmp, feed_out)

if __name__ == "__main__":
	main()
