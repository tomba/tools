#!/usr/bin/python3

# pylint: disable=missing-module-docstring, missing-function-docstring, missing-class-docstring

import argparse
import range_compare

def shorten_commitid(commitid):
    return range_compare.run(f'git rev-parse --short {commitid}')

def is_empty_commit(commitid):
    # XXX is there a better way to detect an empty commit?
    t1 = range_compare.run(f'git rev-parse {commitid}^{{tree}}')
    t2 = range_compare.run(f'git rev-parse {commitid}^^{{tree}}')

    return t1 == t2

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('topic', help='Your topic branch (commit or commit range) (e.g. mybranch or v6.8..mybranch)')
    parser.add_argument('upstream', help='Upstream (commit or commit range) (e.g. v6.10 or v6.9..v6.10)')
    parser.add_argument('-a', '--all', action='store_true', default=False, help='Show also upstreamed commits in range')
    parser.add_argument('-v', '--verbose', action='store_true', default=False)
    args = parser.parse_args()

    range_compare.VERBOSE = args.verbose

    topic_head = range_compare.run(f'git rev-list -1 {args.topic}')
    upstream_head = range_compare.run(f'git rev-list -1 {args.upstream}')
    merge_base = range_compare.run(f'git merge-base {topic_head} {upstream_head}')

    branches = {
        'topic': f'{args.topic} ^{merge_base}',
        'upstream': f'{args.upstream} ^{merge_base}',
    }

    datas = range_compare.range_compare(branches, show_only_branch='topic',
                                        match_by_title=True, drop_common=not args.all)

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
