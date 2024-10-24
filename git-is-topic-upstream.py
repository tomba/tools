#!/usr/bin/python3

# pylint: disable=missing-module-docstring, missing-function-docstring, missing-class-docstring

import argparse
import range_compare
import time

from xtermcolor import colorize

def is_empty_commit(commitid):
    # XXX is there a better way to detect an empty commit?
    t1 = range_compare.run(f'git rev-parse {commitid}^{{tree}}')
    t2 = range_compare.run(f'git rev-parse {commitid}^^{{tree}}')

    return t1 == t2

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('left', nargs='?', default='HEAD', help='Commit or commit range (e.g. mybranch or v6.8..mybranch) (default=HEAD)')
    parser.add_argument('right', help='Commit or commit range (e.g. v6.10 or v6.9..v6.10)')
    parser.add_argument('-a', '--all', action='store_true', default=False, help='Show also common commits')
    parser.add_argument('-v', '--verbose', action='store_true', default=False)
    parser.add_argument('-l', '--left-only', action='store_true', default=False, help='Show only commits in left')
    parser.add_argument('-r', '--right-only', action='store_true', default=False, help='Show only commits in right')
    args = parser.parse_args()

    range_compare.VERBOSE = args.verbose

    left_head = range_compare.run(f'git rev-list -1 {args.left}')
    right_head = range_compare.run(f'git rev-list -1 {args.right}')
    merge_base = range_compare.run(f'git merge-base {left_head} {right_head}')

    branches = {
        'left': f'{args.left} ^{merge_base}',
        'right': f'{args.right} ^{merge_base}',
    }

    datas = range_compare.range_compare(branches, show_only_branch=[],
                                        match_by_title=True, drop_common=not args.all)

    commitid_len = 0

    shown_commits = set()

    lines = []

    if args.verbose:
        print(f'Processing {len(datas)} entries')

    timestamp = 0
    for i, data in enumerate(datas):
        if time.time() > timestamp + 10:
            if args.verbose:
                print(f'  {i}/{len(datas)}')
            timestamp = time.time()

        commitid = data.commitid

        #if is_empty_commit(commitid):
        #    continue

        in_left = 'left' in data.found
        in_right = 'right' in data.found

        if in_left and in_right:
            # Track commits that are in both branches, and skip when we find
            # it the second time
            lcommit = data.found['left'][0]

            if lcommit in shown_commits:
                continue

            shown_commits.add(lcommit)

        if in_left:
            lcommit = data.found['left'][0]
        else:
            lcommit = ''

        if in_right:
            rcommit = data.found['right'][0]
        else:
            rcommit = ''

        if in_left and in_right:
            side = '='
            c = 0xaaaaaa
            match_type = data.found['right'][1][0]
        elif in_left:
            side = '<'
            c = 0xffaaaa
            match_type = ' '

            if args.right_only:
                continue

        elif in_right:
            side = '>'
            c = 0xaaffaa
            match_type = ' '

            if args.left_only:
                continue
        else:
            raise RuntimeError()

        if lcommit:
            lcommit = range_compare.shorten_commitid(lcommit)

        if rcommit:
            rcommit = range_compare.shorten_commitid(rcommit)

        if not commitid_len:
            commitid_len = max(len(lcommit), len(rcommit))

        s = f'{side} {match_type} {lcommit:{commitid_len}} {rcommit:{commitid_len}} {data.title}'

        lines.append(colorize(s, rgb=c))

    for l in lines:
        print(l)

if __name__=='__main__':
    main()
