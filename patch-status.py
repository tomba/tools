#!/usr/bin/python3

import subprocess
from subprocess import PIPE
import pygit2
import pickle
import os
import csv
import time
from collections import defaultdict

#from patch_status_ti import *
from patch_status_renesas import *
#from patch_status_cruise import *

# output file
OUT_FILE = "patch-status.csv"

# File used to cache data between runs
COMMIT_CACHE_FILE="/home/tomba/work/patch-status.cache"

# Optional file where old custom column data will be read from
OLD_COMMIT_FILE = None
#OLD_COMMIT_FILE = 'patch-status-2.csv'

# Columns handled by this script
AUTO_COLUMNS = ["Number", "Commit", "Title", "Author", "Committer", "Category",
	"Upstream Commit", "Upstream Found by", "Upstream Range"]

PATHS = tuple(PATHS) # must be tuple

repo = pygit2.Repository(".")

def runasync(cmd):
	return subprocess.Popen(cmd, stdout=PIPE, shell=True, universal_newlines=True)

def run(cmd):
	return subprocess.run(cmd, check=True, stdout=PIPE, shell=True, universal_newlines=True).stdout

# commitid : { "patchid": patch-id, "title": title, "files": [ files ] }
commit_map = {}

def get_entry(oid):
	id = str(oid)
	d = commit_map.get(id)
	if d == None:
		d = {}
		commit_map[id] = d
	return d

def get_patch_id(oid):
	d = get_entry(oid)

	id = d.get("patchid")
	if id == None:
		id = run("git show --no-decorate {} | git patch-id --stable".format(oid)).strip().split(" ")[0]
		d["patchid"] = id

	return id

def get_title(oid):
	d = get_entry(oid)

	title = d.get("title")
	if title == None:
		title = repo.get(oid).message.split("\n", 1)[0]
		d["title"] = title

	return title

def get_files(oid):
	d = get_entry(oid)

	files = d.get("files")
	if files == None:
		files = run("git diff-tree --no-commit-id --name-only -r {}".format(oid))
		files = files.rstrip().split("\n")
		d["files"] = files

	return files

def filter_commit_by_people(cid):
	commit = repo.get(cid)
	return (commit.committer.email in PEOPLE) or (commit.author.email in PEOPLE)

def filter_commit_by_path(cid):
	return any(file.startswith(tuple(PATHS)) for file in get_files(cid))

def filter_commit(cid):
	if filter_commit_by_people(cid) or filter_commit_by_path(cid):
		return True

	if len(PEOPLE) == 0 and len(PATHS) == 0:
		return True

	return False

	#return filter_commit_by_path(cid)

def load_cache():
	global commit_map

	if os.path.isfile(COMMIT_CACHE_FILE):
		with open(COMMIT_CACHE_FILE, 'rb') as handle:
			commit_map = pickle.load(handle)
		print("Cache loaded with {} commits".format(len(commit_map)))

def save_cache():
	global commit_map

	with open(COMMIT_CACHE_FILE, 'wb') as handle:
		pickle.dump(commit_map, handle)

	print("Cache saved with {} commits".format(len(commit_map)))

def collect_commits(range):
	print("Collecting commits {}".format(range))

	list = []

	proc = runasync("git rev-list --reverse --no-merges {}".format(range))

	while True:
		line = proc.stdout.readline()
		if line == '' and proc.poll() != None:
			break

		line = line.rstrip()

		list.append(pygit2.Oid(hex=line))

	print("  Found {} commits".format(len(list)))

	return list;

old_commits = {}
old_extra_columns = []

def load_old():
	global old_commits
	global old_extra_columns

	if OLD_COMMIT_FILE == None:
		return

	if not os.path.isfile(OLD_COMMIT_FILE):
		return

	with open(OLD_COMMIT_FILE, newline='') as csvfile:
		reader = csv.DictReader(csvfile, delimiter='\t')

		# column titles not in AUTO_COLUMNS
		extra_columns = [e for e in reader.fieldnames if e not in AUTO_COLUMNS]
		old_extra_columns = extra_columns


		for row in reader:
			commit = row["Commit"]

			data = {}
			for column in extra_columns:
				data[column] = row[column]

			old_commits[commit] = data

	print("Loaded {} old entries from '{}'".format(len(old_commits), OLD_COMMIT_FILE))

def drop_duplicates(commits):
	l = []
	s = set()
	num = 0
	for cid in commits:
		pid = get_patch_id(cid)
		if pid in s:
			title = repo.get(cid).message.split("\n", 1)[0]
			num += 1
			continue

		s.add(pid)
		l.append(cid)

	print("Dropped {} duplicates".format(num))

	return l

# Main code

load_old()

load_cache()

vendor_commits = collect_commits(VENDOR)
vendor_commits = drop_duplicates(vendor_commits)

print("Filtering interesting commits...")
vendor_commits = [cid for cid in vendor_commits if filter_commit(cid)]
print("  found {} interesting commits".format(len(vendor_commits)))

upstream_commits = { tree: [cid for cid in collect_commits(tree)] for tree in UPSTREAMS }
flattened = [i for sublist in [upstream_commits[k] for k in upstream_commits] for i in sublist]

print("generating { patchid: [commitid, ...] }")
patchid_map = defaultdict(set)
i = 0
timestamp = 0
for cid in flattened:
	if time.time() > timestamp + 10:
		print("  {}/{}".format(i, len(flattened)))
		timestamp = time.time()
	i += 1
	pid = get_patch_id(cid)
	patchid_map[pid].add(cid)

print("generating { title: [commitid, ...] }")
title_map = defaultdict(set)
i = 0
timestamp = 0
for cid in flattened:
	if time.time() > timestamp + 10:
		print("  {}/{}".format(i, len(flattened)))
		timestamp = time.time()
	i += 1
	title = get_title(cid)
	title_map[title].add(cid)

save_cache()

print("Creating " + OUT_FILE)

num_in_target = defaultdict(int)

def get_upstream_range(oid):
	assert(oid in flattened)

	for k in UPSTREAMS:
		if oid in upstream_commits[k]:
			return k

	assert(False)

def search_for_commit(oid):
	if oid in flattened:
		return (oid, "Merge", get_upstream_range(oid))

	pid = get_patch_id(oid)
	if pid in patchid_map:
		if len(patchid_map[pid]) > 1:
			print("WARNING: multiple matching commits for the same patch-id (picking the first one)")
			for ucid in patchid_map[pid]:
				print("  ", ucid, get_upstream_range(ucid))

		ucid = list(patchid_map[pid])[0]
		return (ucid, "PatchID", get_upstream_range(ucid))

	title = get_title(oid)
	if title in title_map:
		if len(title_map[title]) > 1:
			print("WARNING: multiple matching commits for the same title (picking the first one)")
			for ucid in title_map[title]:
				print("  ", ucid, get_upstream_range(ucid))

		ucid = list(title_map[title])[0]
		return (ucid, "Title", get_upstream_range(ucid))

	return (None, None, None)

with open(OUT_FILE, 'w', newline='') as csvfile:

	writer = csv.writer(csvfile, quoting=csv.QUOTE_NONNUMERIC)

	writer.writerow(AUTO_COLUMNS + old_extra_columns)

	last = time.time()
	i = 0
	for oid in vendor_commits:
		i = i + 1

		commit = repo.get(oid)

		upoid, found, uprange = search_for_commit(oid)

		if upoid != None:
			num_in_target[uprange] += 1

			if uprange in DROP_UPSTREAMED:
				continue

		files = get_files(oid)
		category = ""
		for cat, paths in CATEGORIES.items():
			if any(file.startswith(paths) for file in files):
				category = cat
				break

		# AUTO_COLUMNS
		data = [ i, oid, get_title(oid), commit.author.name, commit.committer.name, category,
			upoid, found, uprange ]

		old = old_commits.get(str(oid))
		if old != None:
			for column in old_extra_columns:
				data += [ old[column] ]

		writer.writerow(data)

		if time.time() > last + 5:
			print("  {}/{}".format(i, len(vendor_commits)))
			last = time.time()

	print("  {}/{}".format(len(vendor_commits), len(vendor_commits)))

save_cache()

print("Total {} commits".format(len(vendor_commits)))
for k,v in num_in_target.items():
	print("{}: {}".format(k, v))
