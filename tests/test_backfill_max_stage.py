"""
Tests for scripts/backfill_max_stage.py - pure logic plus moto runs.
Run: python -m pytest tests/test_backfill_max_stage.py -v
"""
import os
import sys
import uuid
import importlib.util

import boto3
from moto import mock_aws

_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'backfill_max_stage.py'))
_spec = importlib.util.spec_from_file_location('backfill_max_stage', _path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['backfill_max_stage'] = _mod
_spec.loader.exec_module(_mod)

compute_max_stage = _mod.compute_max_stage
plan_update = _mod.plan_update
run_backfill = _mod.run_backfill

T1 = '2024-01-01T10:00:00+00:00'
T2 = '2024-01-02T10:00:00+00:00'
T3 = '2024-01-03T10:00:00+00:00'


def ev(frm, to, ts):
    return {'fromStatus': frm, 'toStatus': to, 'createdAt': ts}


# ── compute_max_stage ─────────────────────────────────────────────────────────

class TestComputeMaxStage:

    def test_no_events_applied(self):
        assert compute_max_stage([], 'applied') == ('applied', None)

    def test_interview_then_rejected_keeps_interview(self):
        events = [ev(None, 'applied', T1), ev('applied', 'interview', T2), ev('interview', 'rejected', T3)]
        assert compute_max_stage(events, 'rejected') == ('interview', T2)

    def test_direct_rejection_stays_applied_without_first_response(self):
        events = [ev(None, 'applied', T1), ev('applied', 'rejected', T2)]
        assert compute_max_stage(events, 'rejected') == ('applied', None)

    def test_from_status_reveals_stage_when_history_is_missing(self):
        # no event ever moved INTO screened, but one moved OUT of it
        assert compute_max_stage([ev('screened', 'rejected', T2)], 'rejected') == ('screened', None)

    def test_earliest_staged_event_wins_regardless_of_input_order(self):
        events = [ev('screened', 'interview', T3), ev('applied', 'screened', T2)]
        assert compute_max_stage(events, 'interview') == ('interview', T2)

    def test_current_status_counts_when_there_are_no_events(self):
        assert compute_max_stage([], 'interview') == ('interview', None)

    def test_withdrawn_after_offer_keeps_offer(self):
        events = [ev(None, 'applied', T1), ev('applied', 'offer', T2), ev('offer', 'withdrawn', T3)]
        assert compute_max_stage(events, 'withdrawn') == ('offer', T2)

    def test_unknown_statuses_are_ignored(self):
        assert compute_max_stage([ev(None, 'bogus', T1)], 'also-bogus') == ('applied', None)


# ── plan_update ───────────────────────────────────────────────────────────────

class TestPlanUpdate:

    def test_missing_fields_are_written(self):
        assert plan_update({}, 'interview', T2) == {'maxStage': 'interview', 'firstResponseAt': T2}

    def test_correct_item_needs_nothing(self):
        item = {'maxStage': 'interview', 'firstResponseAt': T2}
        assert plan_update(item, 'interview', T2) == {}

    def test_never_lowers_existing_max_stage(self):
        assert plan_update({'maxStage': 'offer'}, 'screened', None) == {}

    def test_does_not_write_first_response_when_none_computed(self):
        assert plan_update({}, 'applied', None) == {'maxStage': 'applied'}

    def test_differing_first_response_is_overwritten(self):
        item = {'maxStage': 'screened', 'firstResponseAt': T3}
        assert plan_update(item, 'screened', T2) == {'firstResponseAt': T2}


# ── moto runs ─────────────────────────────────────────────────────────────────

def create_table(dynamodb):
    return dynamodb.create_table(
        TableName='applytic',
        KeySchema=[{'AttributeName': 'PK', 'KeyType': 'HASH'}, {'AttributeName': 'SK', 'KeyType': 'RANGE'}],
        AttributeDefinitions=[
            {'AttributeName': 'PK', 'AttributeType': 'S'}, {'AttributeName': 'SK', 'AttributeType': 'S'},
            {'AttributeName': 'GSI1PK', 'AttributeType': 'S'}, {'AttributeName': 'GSI1SK', 'AttributeType': 'S'},
        ],
        GlobalSecondaryIndexes=[{
            'IndexName': 'GSI1',
            'KeySchema': [{'AttributeName': 'GSI1PK', 'KeyType': 'HASH'}, {'AttributeName': 'GSI1SK', 'KeyType': 'RANGE'}],
            'Projection': {'ProjectionType': 'ALL'},
        }],
        BillingMode='PAY_PER_REQUEST',
    )


def put_app(table, user, app_id, status, **extra):
    table.put_item(Item={
        'PK': f'USER#{user}', 'SK': f'APP#{app_id}', 'userId': user, 'appId': app_id,
        'status': status, 'entityType': 'APPLICATION', 'updatedAt': 'ORIGINAL', **extra,
    })


def put_event(table, user, app_id, frm, to, ts):
    table.put_item(Item={
        'PK': f'APP#{app_id}', 'SK': f'EVENT#{ts}#{uuid.uuid4()}', 'userId': user,
        'fromStatus': frm, 'toStatus': to, 'createdAt': ts, 'entityType': 'STATUS_EVENT',
    })


def seed_mixed(table):
    put_app(table, 'u1', 'app-1', 'rejected')   # interview then rejected
    put_event(table, 'u1', 'app-1', None, 'applied', T1)
    put_event(table, 'u1', 'app-1', 'applied', 'interview', T2)
    put_event(table, 'u1', 'app-1', 'interview', 'rejected', T3)

    put_app(table, 'u1', 'app-2', 'rejected')   # direct rejection
    put_event(table, 'u1', 'app-2', None, 'applied', T1)
    put_event(table, 'u1', 'app-2', 'applied', 'rejected', T2)

    put_app(table, 'u1', 'app-3', 'applied')
    put_event(table, 'u1', 'app-3', None, 'applied', T1)

    put_app(table, 'u2', 'app-4', 'screened')
    put_event(table, 'u2', 'app-4', None, 'applied', T1)
    put_event(table, 'u2', 'app-4', 'applied', 'screened', T2)


def get_app(table, user, app_id):
    return table.get_item(Key={'PK': f'USER#{user}', 'SK': f'APP#{app_id}'})['Item']


def quiet(*_a, **_k):
    pass


class TestRunBackfill:

    def test_dry_run_writes_nothing(self):
        with mock_aws():
            table = create_table(boto3.resource('dynamodb', region_name='us-east-1'))
            seed_mixed(table)
            result = run_backfill(table, dry_run=True, log=quiet)
            assert result['stats']['scanned'] == 4
            assert result['stats']['to_update'] == 4
            assert result['stats']['updated'] == 0
            assert 'maxStage' not in get_app(table, 'u1', 'app-1')

    def test_apply_writes_expected_values(self):
        with mock_aws():
            table = create_table(boto3.resource('dynamodb', region_name='us-east-1'))
            seed_mixed(table)
            run_backfill(table, dry_run=False, log=quiet)
            a1 = get_app(table, 'u1', 'app-1')
            assert a1['maxStage'] == 'interview' and a1['firstResponseAt'] == T2
            a2 = get_app(table, 'u1', 'app-2')
            assert a2['maxStage'] == 'applied' and 'firstResponseAt' not in a2
            assert get_app(table, 'u1', 'app-3')['maxStage'] == 'applied'
            a4 = get_app(table, 'u2', 'app-4')
            assert a4['maxStage'] == 'screened' and a4['firstResponseAt'] == T2

    def test_second_run_is_a_no_op(self):
        with mock_aws():
            table = create_table(boto3.resource('dynamodb', region_name='us-east-1'))
            seed_mixed(table)
            run_backfill(table, dry_run=False, log=quiet)
            second = run_backfill(table, dry_run=False, log=quiet)
            assert second['stats']['to_update'] == 0
            assert second['stats']['unchanged'] == 4

    def test_updated_at_is_not_touched(self):
        with mock_aws():
            table = create_table(boto3.resource('dynamodb', region_name='us-east-1'))
            seed_mixed(table)
            run_backfill(table, dry_run=False, log=quiet)
            assert get_app(table, 'u1', 'app-1')['updatedAt'] == 'ORIGINAL'

    def test_user_scope_leaves_other_users_alone(self):
        with mock_aws():
            table = create_table(boto3.resource('dynamodb', region_name='us-east-1'))
            seed_mixed(table)
            result = run_backfill(table, user_id='u1', dry_run=False, log=quiet)
            assert result['stats']['scanned'] == 3
            assert 'maxStage' in get_app(table, 'u1', 'app-1')
            assert 'maxStage' not in get_app(table, 'u2', 'app-4')

    def test_invariant_holds_and_rate_rises(self):
        with mock_aws():
            table = create_table(boto3.resource('dynamodb', region_name='us-east-1'))
            seed_mixed(table)
            result = run_backfill(table, dry_run=True, log=quiet)
            assert result['violations'] == []
            u1 = result['per_user']['u1']
            assert u1['old'] == 0 and u1['new'] == 1  # rejected-after-interview now counts
            assert u1['new'] >= u1['old']

    def test_counts_direct_rejections(self):
        with mock_aws():
            table = create_table(boto3.resource('dynamodb', region_name='us-east-1'))
            seed_mixed(table)
            assert run_backfill(table, dry_run=True, log=quiet)['stats']['direct_rejections'] == 1

    def test_existing_higher_max_stage_is_not_lowered(self):
        with mock_aws():
            table = create_table(boto3.resource('dynamodb', region_name='us-east-1'))
            put_app(table, 'u1', 'app-5', 'rejected', maxStage='offer')
            put_event(table, 'u1', 'app-5', None, 'applied', T1)
            put_event(table, 'u1', 'app-5', 'applied', 'rejected', T2)
            result = run_backfill(table, dry_run=False, log=quiet)
            assert result['stats']['to_update'] == 0
            assert get_app(table, 'u1', 'app-5')['maxStage'] == 'offer'

    def test_application_without_events_uses_current_status(self):
        with mock_aws():
            table = create_table(boto3.resource('dynamodb', region_name='us-east-1'))
            put_app(table, 'u1', 'app-6', 'interview')
            run_backfill(table, dry_run=False, log=quiet)
            item = get_app(table, 'u1', 'app-6')
            assert item['maxStage'] == 'interview' and 'firstResponseAt' not in item