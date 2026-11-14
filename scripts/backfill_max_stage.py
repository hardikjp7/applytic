"""
Applytic - maxStage backfill (v3.3.0)

Sets `maxStage` and `firstResponseAt` on existing applications, using their
STATUS_EVENT history as the source of truth.

  maxStage         highest staged status ever reached (applied < screened <
                   interview < offer). rejected / withdrawn are not stages.
  firstResponseAt  createdAt of the earliest event whose toStatus is screened
                   or beyond.

Safe to re-run: it writes only when the computed value differs or the field is
missing, never lowers an existing maxStage, and never touches updatedAt (the
digest and the Dashboard both sort or filter on it).

Usage:
    python backfill_max_stage.py --user-id YOUR_COGNITO_SUB --dry-run
    python backfill_max_stage.py --all --dry-run
    python backfill_max_stage.py --all            # asks for confirmation (--yes skips it)

Known limits:
  - An application created or CSV-imported directly as `rejected` has no staged
    history, so it is treated as stage `applied` (a direct rejection).
  - Legacy items with no events at all get maxStage from their current status
    only, and no firstResponseAt.
"""

import argparse
import sys

import boto3
from boto3.dynamodb.conditions import Key, Attr

TABLE_NAME = 'applytic'
REGION = 'us-east-1'

STAGE_RANK = {'applied': 0, 'screened': 1, 'interview': 2, 'offer': 3}
LEGACY_RESPONDED = {'screened', 'interview', 'offer'}  # the old status-based definition


def get_table():
    return boto3.resource('dynamodb', region_name=REGION).Table(TABLE_NAME)


# ── Pure logic ────────────────────────────────────────────────────────────────

def compute_max_stage(events, status):
    """
    Returns (max_stage, first_response_at).

    Considers the current status plus both fromStatus and toStatus of every
    event, so a missing event cannot hide a stage that a later event reveals.
    first_response_at is the earliest createdAt of an event whose toStatus is
    screened or beyond, or None. Timestamps are ISO-8601 strings in one format
    (as written by now_iso), so string comparison orders them correctly.
    """
    best = 'applied'
    first_response_at = None

    def consider(s):
        nonlocal best
        if s in STAGE_RANK and STAGE_RANK[s] > STAGE_RANK[best]:
            best = s

    consider(status)
    for ev in events:
        consider(ev.get('fromStatus'))
        consider(ev.get('toStatus'))
        if STAGE_RANK.get(ev.get('toStatus'), 0) >= 1:
            ts = ev.get('createdAt')
            if ts and (first_response_at is None or ts < first_response_at):
                first_response_at = ts

    return best, first_response_at


def plan_update(item, max_stage, first_response_at):
    """Attributes that need writing for this item ({} when it is already correct)."""
    updates = {}

    existing = item.get('maxStage')
    # Never lower a value written by a live status change after the deploy
    if existing in STAGE_RANK and STAGE_RANK[existing] > STAGE_RANK[max_stage]:
        max_stage = existing
    if existing != max_stage:
        updates['maxStage'] = max_stage

    if first_response_at and item.get('firstResponseAt') != first_response_at:
        updates['firstResponseAt'] = first_response_at

    return updates


# ── DynamoDB helpers ──────────────────────────────────────────────────────────

def iter_items(method, **kwargs):
    """Yield every item of a query/scan, following LastEvaluatedKey."""
    while True:
        resp = method(**kwargs)
        yield from resp.get('Items', [])
        last = resp.get('LastEvaluatedKey')
        if not last:
            return
        kwargs['ExclusiveStartKey'] = last


def iter_applications(table, user_id=None):
    if user_id:
        return iter_items(
            table.query,
            KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') & Key('SK').begins_with('APP#'),
            FilterExpression=Attr('entityType').eq('APPLICATION'),
        )
    return iter_items(table.scan, FilterExpression=Attr('entityType').eq('APPLICATION'))


def fetch_events(table, app_id):
    return list(iter_items(
        table.query,
        KeyConditionExpression=Key('PK').eq(f'APP#{app_id}') & Key('SK').begins_with('EVENT#'),
    ))


def apply_update(table, user_id, app_id, updates):
    table.update_item(
        Key={'PK': f'USER#{user_id}', 'SK': f'APP#{app_id}'},
        UpdateExpression='SET ' + ', '.join(f'#{k} = :{k}' for k in updates),
        ExpressionAttributeNames={f'#{k}': k for k in updates},
        ExpressionAttributeValues={f':{k}': v for k, v in updates.items()},
        ConditionExpression='attribute_exists(PK)',  # never create an item
    )


# ── Runner ────────────────────────────────────────────────────────────────────

def run_backfill(table, user_id=None, dry_run=True, log=print):
    stats = {
        'scanned': 0, 'to_update': 0, 'updated': 0, 'unchanged': 0,
        'max_stage_set': 0, 'first_response_set': 0,
        'direct_rejections': 0, 'errors': 0,
    }
    per_user = {}
    violations = []

    for item in iter_applications(table, user_id):
        stats['scanned'] += 1
        app_id, owner = item.get('appId'), item.get('userId')
        if not app_id or not owner:
            stats['errors'] += 1
            log(f'  ERROR: application item without appId/userId: {item.get("PK")} {item.get("SK")}')
            continue

        status = item.get('status', 'applied')
        max_stage, first_response_at = compute_max_stage(fetch_events(table, app_id), status)
        updates = plan_update(item, max_stage, first_response_at)
        final_stage = updates.get('maxStage', item.get('maxStage'))

        # Invariant: the new definition must never respond less than the old one
        old_responded = status in LEGACY_RESPONDED
        new_responded = STAGE_RANK.get(final_stage, 0) >= 1
        u = per_user.setdefault(owner, {'total': 0, 'old': 0, 'new': 0})
        u['total'] += 1
        u['old'] += int(old_responded)
        u['new'] += int(new_responded)
        if old_responded and not new_responded:
            violations.append(app_id)

        if status == 'rejected' and final_stage == 'applied':
            stats['direct_rejections'] += 1

        if not updates:
            stats['unchanged'] += 1
            continue

        stats['to_update'] += 1
        stats['max_stage_set'] += int('maxStage' in updates)
        stats['first_response_set'] += int('firstResponseAt' in updates)
        if not dry_run:
            try:
                apply_update(table, owner, app_id, updates)
                stats['updated'] += 1
            except Exception as e:  # keep going, report at the end
                stats['errors'] += 1
                log(f'  ERROR {app_id}: {e}')

    return {'stats': stats, 'per_user': per_user, 'violations': violations}


def _pct(n, d):
    return f'{round(n / d * 100, 1)}%' if d else '-'


def print_report(result, dry_run, log=print):
    s = result['stats']
    log('')
    log(f'Applications scanned:        {s["scanned"]}')
    log(f'Need an update:              {s["to_update"]}  '
        f'(maxStage: {s["max_stage_set"]}, firstResponseAt: {s["first_response_set"]})')
    log(f'Already correct:             {s["unchanged"]}')
    log(f'Direct rejections (applied): {s["direct_rejections"]}')
    log(f'Written:                     {s["updated"]}' + ('   (dry run - nothing written)' if dry_run else ''))
    log(f'Errors:                      {s["errors"]}')
    log('')
    log(f'{"user":40} {"apps":>5} {"old rate":>9} {"new rate":>9}')
    for uid, u in sorted(result['per_user'].items()):
        log(f'{uid:40} {u["total"]:>5} {_pct(u["old"], u["total"]):>9} {_pct(u["new"], u["total"]):>9}')
    log('')
    if result['violations']:
        log(f'INVARIANT VIOLATED for {len(result["violations"])} application(s) - do not proceed:')
        for app_id in result['violations']:
            log(f'  {app_id}')
    else:
        log('Invariant holds: no application responds less under the new definition.')


def main():
    parser = argparse.ArgumentParser(description='Backfill maxStage / firstResponseAt on applications')
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument('--user-id', help='Only this Cognito sub')
    scope.add_argument('--all', action='store_true', help='Every user')
    parser.add_argument('--dry-run', action='store_true', help='Report only, write nothing')
    parser.add_argument('--yes', action='store_true', help='Skip the confirmation prompt')
    args = parser.parse_args()

    if not args.dry_run and not args.yes:
        scope_text = f'user {args.user_id}' if args.user_id else 'ALL users'
        print(f'About to WRITE to table "{TABLE_NAME}" ({REGION}) for {scope_text}.')
        if input("Type 'yes' to continue: ").strip().lower() != 'yes':
            print('Aborted.')
            return 1

    result = run_backfill(get_table(), user_id=args.user_id, dry_run=args.dry_run)
    print_report(result, args.dry_run)

    if result['violations']:
        return 2
    return 1 if result['stats']['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())