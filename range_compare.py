#!/usr/bin/python3

# pylint: disable=missing-module-docstring, missing-function-docstring, missing-class-docstring

import pickle
import subprocess
import time

from collections import defaultdict
from pathlib import Path
from subprocess import PIPE

VERBOSE = False

# File used to cache data between runs
COMMIT_CACHE_FILE = Path.home() / '.cache/patch-status.cache'

def runasync(cmd):
    return subprocess.Popen(cmd, stdout=PIPE, shell=True, universal_newlines=True)

def run(cmd):
    return subprocess.run(cmd, check=True, stdout=PIPE, shell=True, universal_newlines=True).stdout.strip()

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

        patchid = run(f'git show --no-decorate {commitid} | git patch-id --stable').split(' ')[0]
        title = run(f'git log --format=%s -n 1 {commitid}')

        self.commit_map[commitid] = { 'patchid': patchid, 'title': title, }

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

    def get_files(self, commitid: str) -> list[str]:
        if 'files' not in self.commit_map[commitid]:
            files = run(f'git diff-tree --no-commit-id --name-only -r {commitid}').split('\n')
            self.commit_map[commitid]['files'] = files

        return self.commit_map[commitid]['files']

    def load(self):
        if COMMIT_CACHE_FILE.is_file():
            with open(COMMIT_CACHE_FILE, 'rb') as handle:
                data = pickle.load(handle)
                self.commit_map, self.patchid_idx, self.title_idx = data
            if VERBOSE:
                print(f'Cache loaded with {len(self.commit_map)} commits')

    def save(self):
        with open(COMMIT_CACHE_FILE, 'wb') as handle:
            data = (self.commit_map, self.patchid_idx, self.title_idx)
            pickle.dump(data, handle)

        if VERBOSE:
            print(f'Cache saved with {len(self.commit_map)} commits')


def collect_commits(commitrange):
    if VERBOSE:
        print(f'Collecting commits {commitrange}: ', end='')

    proc = runasync(f'git rev-list --no-merges {commitrange}')

    commits = []

    while True:
        line = proc.stdout.readline()
        if line == '' and proc.poll() is not None:
            break

        line = line.rstrip()

        commits.append(line)

    if VERBOSE:
        print(f'{len(commits)} commits')

    return commits

def shorten_commitid(commitid):
    return run(f'git rev-parse --short {commitid}')

def range_compare(branches, show_only_branch, match_by_title, drop_common):
    # Collect commits

    # { branch-name: [commits]}
    branches = { name: collect_commits(range) for name,range in branches.items() }

    # Flattened list of all commits
    flattened = [item for sublist in branches.values() for item in sublist]

    if VERBOSE:
        print('Generating database')

    # Load cache and add commits to cache (this may take a while)

    cache = CommitCache()
    cache.load()

    i = 0
    timestamp = 0
    for commitid in flattened:
        if time.time() > timestamp + 10:
            if VERBOSE:
                print(f'  {i}/{len(flattened)}')
            timestamp = time.time()
        i += 1
        cache.add_commit(commitid)
    if VERBOSE:
        print(f'  {i}/{len(flattened)}')

    cache.save()

    def search_for_commit_in_branch(commitid, branch_name):
        if commitid in branches[branch_name]:
            return (commitid, 'CommitID')

        pid = cache.get_patch_id(commitid)
        for c in cache.get_patch_id_commits(pid):
            if c in branches[branch_name]:
                return (c, 'PatchID')

        if match_by_title:
            title = cache.get_title(commitid)
            for c in cache.get_title_commits(title):
                if c in branches[branch_name]:
                    return (c, 'Title')

        return None

    # Search commits

    if show_only_branch:
        commit_list = branches[show_only_branch]
    else:
        commit_list = flattened

    datas = []

    timestamp = 0
    for i, commitid in enumerate(commit_list):
        if time.time() > timestamp + 10:
            if VERBOSE:
                print(f'  {i}/{len(commit_list)}')
            timestamp = time.time()

        found = {}
        for b in branches:
            res = search_for_commit_in_branch(commitid, b)

            if not res:
                continue

            found[b] = res

        is_common = len(found) == len(branches)
        if drop_common and is_common:
            continue

        data = ( commitid, cache.get_title(commitid), found )

        datas.append(data)

    if VERBOSE:
        print(f'  {len(commit_list)}/{len(commit_list)}')

    return datas
