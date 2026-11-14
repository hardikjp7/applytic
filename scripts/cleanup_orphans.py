"""
Applytic - orphan cleanup (v3.3.0)

Finds APP#{appId} child items (events, notes, contacts, interview prep) whose
parent application no longer exists. These are left behind by deletes made
before v3.3.0 added the cascade.

Every child carries the owner's userId, so the parent is a direct get_item on
USER#{userId} / APP#{appId}. A partition whose children carry no userId cannot
be checked, so it is reported and never deleted.

Dry run by default.

Usage:
    python cleanup_orphans.py                       # report only
    python cleanup_orphans.py --user-id SUB         # report only, one owner
    python cleanup_orphans.py --apply               # delete the orphans

Reads the whole table once (a scan). Fine at this size.
"""

import argparse
import sys
from collections import Counter

import boto3
from boto3.dynamodb.conditions import Attr

TABLE_NAME = 'applytic'
REGION = 'us-east-1'


def get_table():
    return boto3.resource('dynamodb', region_name=REGION).Table(TABLE_NAME)


def iter_items(method, **kwargs):
    while True:
        resp = method(**kwargs)
        yield from resp.get('Items', [])
        last = resp.get('LastEvaluatedKey')
        if not last:
            return
        kwargs['ExclusiveStartKey'] = last


def find_orphans(table, user_id=None):
    """
    Returns {
      'partitions': number of APP# partitions seen,
      'orphans': {appId: {'owner': userId, 'keys': [{PK, SK}, ...]}},
      'unresolvable': [appId, ...],   # no child carried a userId
    }
    """
    partitions = {}
    for item in iter_items(
        table.scan,
        FilterExpression=Attr('PK').begins_with('APP#'),
        ProjectionExpression='PK, SK, userId',
    ):
        part = partitions.setdefault(item['PK'], {'keys': [], 'owner': None})
        part['keys'].append({'PK': item['PK'], 'SK': item['SK']})
        if not part['owner'] and item.get('userId'):
            part['owner'] = item['userId']

    orphans, unresolvable = {}, []
    for pk, part in partitions.items():
        app_id = pk[len('APP#'):]
        owner = part['owner']
        if not owner:
            unresolvable.append(app_id)
            continue
        if user_id and owner != user_id:
            continue
        parent = table.get_item(
            Key={'PK': f'USER#{owner}', 'SK': f'APP#{app_id}'},
            ProjectionExpression='appId',
        )
        if 'Item' not in parent:
            orphans[app_id] = {'owner': owner, 'keys': part['keys']}

    return {'partitions': len(partitions), 'orphans': orphans, 'unresolvable': unresolvable}


def delete_orphans(table, orphans):
    deleted = 0
    with table.batch_writer() as batch:
        for info in orphans.values():
            for key in info['keys']:
                batch.delete_item(Key=key)
                deleted += 1
    return deleted


def main():
    parser = argparse.ArgumentParser(description='Find (and optionally delete) orphaned APP# child items')
    parser.add_argument('--user-id', help='Only orphans owned by this Cognito sub')
    parser.add_argument('--apply', action='store_true', help='Actually delete (default is a dry run)')
    args = parser.parse_args()

    table = get_table()
    result = find_orphans(table, user_id=args.user_id)
    orphans = result['orphans']
    item_count = sum(len(o['keys']) for o in orphans.values())

    print(f'\nAPP# partitions scanned: {result["partitions"]}')
    print(f'Orphaned applications:   {len(orphans)}  ({item_count} items)')
    for app_id, info in sorted(orphans.items()):
        kinds = Counter(k['SK'].split('#')[0] for k in info['keys'])
        detail = ', '.join(f'{k} x{n}' for k, n in sorted(kinds.items()))
        print(f'  {app_id}  owner={info["owner"]}  {detail}')
    if result['unresolvable']:
        print(f'\nCannot verify (children carry no userId) - left untouched: {len(result["unresolvable"])}')
        for app_id in result['unresolvable']:
            print(f'  {app_id}')

    if not orphans:
        print('\nNothing to clean up.')
        return 0
    if not args.apply:
        print('\nDry run - nothing deleted. Re-run with --apply to delete.')
        return 0

    print(f'\nDeleted {delete_orphans(table, orphans)} items.')
    return 0


if __name__ == '__main__':
    sys.exit(main())