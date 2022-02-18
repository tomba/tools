#!/usr/bin/python3

import subprocess
from subprocess import PIPE
import pygit2
import pickle
import csv
import time
from collections import defaultdict
from pathlib import Path

# Branches (ranges) we're interested in
BRANCHES = {
	"Tomi": "v5.16..streams/work",
	"Laurent": "v5.17-rc4..laurent-gitlab/pinchartl/v5.17/streams",
}

# If set, list only commits in the given branch
#SHOW_ONLY_BRANCH = "Tomi"
SHOW_ONLY_BRANCH = None

# Use title matching in addition to commit ID and patch ID
MATCH_BY_TITLE = False

# Drop commits that are found in all branches
DROP_COMMON = False

# output file
OUT_FILE = "branch-status.csv"

# File used to cache data between runs
COMMIT_CACHE_FILE = Path.home() / ".cache/patch-status.cache"

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

def load_cache():
	global commit_map

	if COMMIT_CACHE_FILE.is_file():
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

	proc = runasync("git rev-list --no-merges {}".format(range))

	while True:
		line = proc.stdout.readline()
		if line == '' and proc.poll() != None:
			break

		line = line.rstrip()

		list.append(pygit2.Oid(hex=line))

	print("  Found {} commits".format(len(list)))

	return list;

def main():
	load_cache()

	branches = { name: collect_commits(range) for name,range in BRANCHES.items() }

	flattened = collect_commits(" ".join(BRANCHES.values()))

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
	print("  {}/{}".format(i, len(flattened)))

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
	print("  {}/{}".format(i, len(flattened)))

	save_cache()

	print("Creating " + OUT_FILE)

	num_in_target = defaultdict(int)

	def get_upstream_range(oid):
		assert(oid in flattened)

		for k in UPSTREAMS:
			if oid in upstream_commits[k]:
				return k

		assert(False)

	def search_for_commit_in_branch(oid, branch_name):
		if oid in branches[branch_name]:
			return (oid, "OID")

		pid = get_patch_id(oid)
		for c in patchid_map.get(pid, []):
			if c in branches[branch_name]:
				return (c, "PatchID")

		if MATCH_BY_TITLE:
			title = get_title(oid)
			for c in title_map.get(title, []):
				if c in branches[branch_name]:
					return (c, "Title")

		return (None, None)

	with open(OUT_FILE, 'w', newline='') as csvfile:
		writer = csv.writer(csvfile, quoting=csv.QUOTE_NONNUMERIC)

		cols = []
		for b in branches:
			cols += [b, b]

		writer.writerow(["Title", *cols])

		if SHOW_ONLY_BRANCH:
			commit_list = branches[SHOW_ONLY_BRANCH]
		else:
			commit_list = flattened

		timestamp = 0
		for i, oid in enumerate(commit_list):
			if time.time() > timestamp + 10:
				print("  {}/{}".format(i, len(commit_list)))
				timestamp = time.time()

			commit = repo.get(oid)

			found = [search_for_commit_in_branch(oid, b) for b in branches]

			is_common = all(x != (None, None) for x in found)

			if DROP_COMMON and is_common:
				continue

			columns = [c for l in found for c in l]

			data = [ get_title(oid), *columns ]

			writer.writerow(data)

		print("  {}/{}".format(len(commit_list), len(commit_list)))

	save_cache()

	print("Total {} commits".format(len(commit_list)))
	for k,v in num_in_target.items():
		print("{}: {}".format(k, v))


if __name__=="__main__":
    main()
