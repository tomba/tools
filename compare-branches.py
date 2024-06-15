#!/usr/bin/python3

# pylint: disable=missing-module-docstring, missing-function-docstring, missing-class-docstring

import csv
import pickle
import subprocess
import time

from collections import defaultdict
from pathlib import Path
from subprocess import PIPE

# Branches (ranges) we're interested in
BRANCHES = {
    'rpi': 'v6.8-rc2..rpi/cfe-streams',
    'up': 'v6.9-rc7..b4/rp1-cfe',

#    'Tomi': 'renesas-geert/master..renesas/work',
    #'Upstream': 'renesas-geert/master..v6.9',
#    'Upstream': 'v6.3..v6.4',
}

# If set, list only commits in the given branch
#SHOW_ONLY_BRANCH = 'Tomi'
SHOW_ONLY_BRANCH = None

# Use title matching in addition to commit ID and patch ID
MATCH_BY_TITLE = True

# Drop commits that are found in all branches
DROP_COMMON = False

# output file
OUT_FILE = 'branch-status.csv'

# File used to cache data between runs
COMMIT_CACHE_FILE = Path.home() / '.cache/patch-status.cache'

def runasync(cmd):
    return subprocess.Popen(cmd, stdout=PIPE, shell=True, universal_newlines=True)

def run(cmd):
    return subprocess.run(cmd, check=True, stdout=PIPE, shell=True, universal_newlines=True).stdout

class CommitCache:
    def __init__(self) -> None:
        # commitid : { 'patchid': patch-id, 'title': title, 'files': [ files ] }
        self.commit_map = {}
        # patchid : [ commitid, commitid, ...]
        self.patchid_idx: dict[str, list[str]] = defaultdict(list)
        # title : [ commitid, commitid, ...]
        self.title_idx: dict[str, list[str]] = defaultdict(list)

    def add_commit(self, commitid: str):
        if commitid in self.commit_map:
            return

        patchid = run(f'git show --no-decorate {commitid} | git patch-id --stable').strip().split(' ')[0]
        title = run(f'git log --format=%s -n 1 {commitid}').strip()
        #files = run(f'git diff-tree --no-commit-id --name-only -r {commitid}').rstrip().split('\n')
        files = []

        self.commit_map[commitid] = { 'patchid': patchid, 'title': title, 'files': files }

        self.patchid_idx[patchid].append(commitid)
        self.title_idx[title].append(commitid)

    def get_patch_id(self, commitid: str) -> str:
        return self.commit_map[commitid]['patchid']

    def get_title(self, commitid: str) -> str:
        return self.commit_map[commitid]['title']

    def get_patch_id_commits(self, patchid: str) -> list[str]:
        return self.patchid_idx[patchid]

    def get_title_commits(self, title: str) -> list[str]:
        return self.title_idx[title]

    def load(self):
        if COMMIT_CACHE_FILE.is_file():
            with open(COMMIT_CACHE_FILE, 'rb') as handle:
                data = pickle.load(handle)
                self.commit_map, self.patchid_idx, self.title_idx = data
            print(f'Cache loaded with {len(self.commit_map)} commits')

    def save(self):
        with open(COMMIT_CACHE_FILE, 'wb') as handle:
            data = (self.commit_map, self.patchid_idx, self.title_idx)
            pickle.dump(data, handle)

        print(f'Cache saved with {len(self.commit_map)} commits')


def collect_commits(commitrange):
    print(f'Collecting commits {commitrange}: ', end='')

    proc = runasync(f'git rev-list --no-merges {commitrange}')

    commits = []

    while True:
        line = proc.stdout.readline()
        if line == '' and proc.poll() is not None:
            break

        line = line.rstrip()

        commits.append(line)

    print(f'{len(commits)} commits')

    return commits


def main():
    cache = CommitCache()

    cache.load()

    branches = { name: collect_commits(range) for name,range in BRANCHES.items() }

    flattened = collect_commits(' '.join(BRANCHES.values()))

    print('Generating database')

    i = 0
    timestamp = 0
    for commitid in flattened:
        if time.time() > timestamp + 10:
            print(f'  {i}/{len(flattened)}')
            timestamp = time.time()
        i += 1
        cache.add_commit(commitid)
    print(f'  {i}/{len(flattened)}')

    cache.save()

    print(f'Creating {OUT_FILE}')

    def search_for_commit_in_branch(commitid, branch_name):
        if commitid in branches[branch_name]:
            return (commitid, 'CommitID')

        pid = cache.get_patch_id(commitid)
        for c in cache.get_patch_id_commits(pid):
            if c in branches[branch_name]:
                return (c, 'PatchID')

        if MATCH_BY_TITLE:
            title = cache.get_title(commitid)
            for c in cache.get_title_commits(title):
                if c in branches[branch_name]:
                    return (c, 'Title')

        return (None, None)

    with open(OUT_FILE, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, quoting=csv.QUOTE_NONNUMERIC)

        cols = []
        for b in branches:
            cols += [b, b]

        writer.writerow(['Title', *cols])

        if SHOW_ONLY_BRANCH:
            commit_list = branches[SHOW_ONLY_BRANCH]
        else:
            commit_list = flattened

        timestamp = 0
        for i, commitid in enumerate(commit_list):
            if time.time() > timestamp + 10:
                print(f'  {i}/{len(commit_list)}')
                timestamp = time.time()

            found = [search_for_commit_in_branch(commitid, b) for b in branches]

            is_common = all(x != (None, None) for x in found)

            if DROP_COMMON and is_common:
                continue

            columns = [c for l in found for c in l]

            data = [ cache.get_title(commitid), *columns ]

            writer.writerow(data)

        print(f'  {len(commit_list)}/{len(commit_list)}')

    print(f'Created {OUT_FILE}')
    print(f'Total {len(commit_list)} commits')


if __name__=='__main__':
    main()
