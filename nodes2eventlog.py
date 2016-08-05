#!/usr/bin/python3
# -*- coding: utf-8; -*-

import sys
import os
import os.path
import json
import pickle
import feed.atom
import datetime
import dateutil.parser
import uuid

MAX_LOG_ENTRIES = 10000
MAX_FEED_ENTRIES = 100

MAP_NODE_URL = 'http://vogtland.freifunk.net/map/#!v:m;n:'
OFFLINE_THRESHOLD = 0 # minutes

def load_env_config():
	if 'MAX_LOG_ENTRIES' in os.environ:
		global MAX_LOG_ENTRIES
		MAX_LOG_ENTRIES = int(os.environ['MAX_LOG_ENTRIES'])
		assert MAX_LOG_ENTRIES >= 0

	if 'MAX_FEED_ENTRIES' in os.environ:
		global MAX_FEED_ENTRIES
		MAX_FEED_ENTRIES = int(os.environ['MAX_FEED_ENTRIES'])
		assert MAX_FEED_ENTRIES >= 0

	if 'MAP_NODE_URL' in os.environ:
		global MAP_NODE_URL
		MAP_NODE_URL = os.environ['MAP_NODE_URL']

	if 'OFFLINE_THRESHOLD' in os.environ:
		global OFFLINE_THRESHOLD
		OFFLINE_THRESHOLD = int(os.environ['OFFLINE_THRESHOLD'])
		assert OFFLINE_THRESHOLD >= 0

def load_eventlog(path):
	try:
		return pickle.load(open(path, 'rb'))
	except FileNotFoundError:
		return list()

def load_state(path):
	try:
		return pickle.load(open(path, 'rb'))
	except FileNotFoundError:
		return dict()

def dump_pickle(data, filename):
	with open(filename, 'wb') as f:
		pickle.dump(data, f)
		f.flush()
		os.fsync(f.fileno())

def extract_eventfeed(eventlog):
	xmldoc, events = feed.atom.new_xmldoc_feed()
	events.title = "Freifunk Vogtland Node Events"
	events.id = "urn:uuid:e4aebb54-5a38-11e6-ad9d-507b9dce2683"
	events.updated = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
	author = feed.atom.Author("nodes2eventlog")

	feedlog = eventlog[-MAX_FEED_ENTRIES:]
	feedlog.reverse()

	for event in feedlog:
		entry = feed.atom.Entry()
		entry.title = "[%s] %s" % (event['eventtype'].upper(), event['message'])
		entry.content = "[%s] %s" % (event['eventtype'].upper(), event['message'])
		entry.id = "urn:uuid:" + str(event['uuid'])
		entry.published = event['timestamp'].strftime('%Y-%m-%dT%H:%M:%SZ')
		entry.updated = event['timestamp'].strftime('%Y-%m-%dT%H:%M:%SZ')
		entry.author = author

		if 'url' in event and event['url']:
			entry.links.append(feed.atom.Link(event['url']))

		events.entries.append(entry)

	return xmldoc

def dump_feed(data, filename):
	with open(filename, 'w') as f:
		f.write(str(data))
		f.flush()
		os.fsync(f.fileno())

def mark_nodes(state):
	for nodeid, node in state.items():
		node['available'] = False

def sweep_nodes(state, eventlog):
	filtered_state = {k:v for (k,v) in state.items() if v['available']}

	removed = {k:v for (k,v) in state.items() if not v['available']}
	for node_id, node in removed.items():
		log_event_node(eventlog, datetime.datetime.utcnow(), "drop", node_id, node)

	return dict(filtered_state)

def sanitize_nodestate(nodestate):
	if not 'online' in nodestate:
		nodestate['online'] = False

	if not 'hostname' in nodestate:
		nodestate['hostname'] = ""

def log_event(eventlog, timestamp, eventtype, message, url):
	eventlog.append({
		'timestamp': timestamp,
		'eventtype': eventtype,
		'message': message,
		'url': url,
		'uuid': uuid.uuid4()
	})

def log_event_node(eventlog, timestamp, eventtype, node_id, node_state):
	url = MAP_NODE_URL + node_id
	log_event(eventlog, timestamp, eventtype, node_state['hostname'], url)

def parse_nodestate(nodes, eventlog, state):
	new_node_timelimit = datetime.datetime.utcnow() - datetime.timedelta(14)
	offline_timelimit = datetime.datetime.utcnow() - datetime.timedelta(0, 0, 0, 0, OFFLINE_THRESHOLD)

	for node in nodes['nodes']:
		node_id = node['nodeinfo']['node_id']
		new_node = False
		timestamp = dateutil.parser.parse(node['lastseen'])
		firsttimestamp = dateutil.parser.parse(node['firstseen'])

		if not node_id in state:
			state[node_id] = {}
			if firsttimestamp > new_node_timelimit:
				new_node = True

		sanitize_nodestate(state[node_id])
		oldstate_online = state[node_id]['online']
		oldstate_hostname = state[node_id]['hostname']

		state[node_id]['available'] = True
		state[node_id]['hostname'] = node['nodeinfo']['hostname']

		# only accept changes to online directly
		# or to offline after reaching threshold
		if node['flags']['online'] or offline_timelimit >= timestamp:
			state[node_id]['online'] = node['flags']['online']

		if new_node:
			log_event_node(eventlog, firsttimestamp, "new", node_id, state[node_id])

		if oldstate_online != state[node_id]['online'] or new_node or not state[node_id]['online']:
			if state[node_id]['online']:
				eventtype = "online"
				timestamp = firsttimestamp
			else:
				eventtype = "offline"
				if offline_timelimit < timestamp:
					new_node = False
				else:
					new_node = True

			if new_node:
				log_event_node(eventlog, timestamp, eventtype, node_id, state[node_id])

		if oldstate_hostname != "" and oldstate_hostname != state[node_id]['hostname']:
			url = MAP_NODE_URL + node_id
			log_event(eventlog, timestamp, "RENAME", "%s -> %s" % (oldstate_hostname, state[node_id]['hostname']), url)

def cleanup_eventlog(eventlog):
	eventlog.sort(key=lambda v: v['timestamp'])
	return eventlog[-MAX_LOG_ENTRIES:]

def usage():
	prog = 'nodes2eventlog.py'
	if len(sys.argv) > 0:
		prog = sys.argv[0]

	print('%s IN_NODES_JSON DBPATH OUT_FEED' % (prog))

def main():
	if len(sys.argv) != 4:
		usage()
		sys.exit(1)

	load_env_config()

	nodes_in = sys.argv[1]
	dbpath = sys.argv[2]
	feed_out = sys.argv[3]

	state_path = os.path.join(dbpath, "state.pickle")
	state_outtmp = os.path.join(dbpath, "state.pickle.tmp")
	eventlog_path = os.path.join(dbpath, "eventlog.pickle")
	eventlog_outtmp = os.path.join(dbpath, "eventlog.pickle.tmp")
	feed_outtmp = feed_out + '.tmp'

	# load
	nodes = json.load(open(nodes_in))
	eventlog = load_eventlog(eventlog_path)
	state = load_state(state_path)

	# data crunching
	mark_nodes(state)
	parse_nodestate(nodes, eventlog, state)
	state = sweep_nodes(state, eventlog)

	eventlog = cleanup_eventlog(eventlog)
	eventfeed = extract_eventfeed(eventlog)

	# save
	dump_pickle(state, state_outtmp)
	dump_pickle(eventlog, eventlog_outtmp)
	dump_feed(eventfeed, feed_outtmp)

	os.rename(state_outtmp, state_path)
	os.rename(eventlog_outtmp, eventlog_path)
	os.rename(feed_outtmp, feed_out)

if __name__ == "__main__":
	main()
