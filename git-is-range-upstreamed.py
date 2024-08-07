#!/usr/bin/python3

# pylint: disable=missing-module-docstring, missing-function-docstring, missing-class-docstring

import argparse
import range_compare

parser = argparse.ArgumentParser()
parser.add_argument('range', help='Commit range of your commits (e.g. v6.8..mybranch)')
parser.add_argument('upstream', help='Upstream branch/tag (e.g. v6.10)')
parser.add_argument('-a', '--all', action='store_true', default=False, help='Show also upstreamed commits in range')
args = parser.parse_args()

def shorten_commitid(commitid):
    return range_compare.run(f'git rev-parse --short {commitid}')

def is_empty_commit(commitid):
    # XXX is there a better way to detect an empty commit?
    t1 = range_compare.run(f'git rev-parse {commitid}^{{tree}}')
    t2 = range_compare.run(f'git rev-parse {commitid}^^{{tree}}')

    return t1 == t2

def main():
    head = range_compare.run(f'git rev-list -1 {args.range}')
    merge_base = range_compare.run(f'git merge-base {head} {args.upstream}')

    BRANCHES = {
        'topic': args.range,
        'upstream': f'{merge_base}..{args.upstream}',
    }

    SHOW_ONLY_BRANCH = 'topic'
    MATCH_BY_TITLE = True
    DROP_COMMON = not args.all

    datas = range_compare.range_compare(BRANCHES, SHOW_ONLY_BRANCH, MATCH_BY_TITLE, DROP_COMMON)

    for data in datas:
        commitid = shorten_commitid(data[0])

        if is_empty_commit(commitid):
            continue

        title = data[1]

        print(commitid, title)

        if 'upstream' in data[2]:
            v = data[2]['upstream']
            print(f'  Upstream: {shorten_commitid(v[0])} ({v[1]})')

if __name__=='__main__':
    main()
