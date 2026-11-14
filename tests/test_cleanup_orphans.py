"""
Tests for scripts/cleanup_orphans.py (moto).
Run: python -m pytest tests/test_cleanup_orphans.py -v
"""
import os
import sys
import importlib.util

import boto3
from boto3.dynamodb.conditions import Key
from moto import mock_aws

_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'cleanup_orphans.py'))
_spec = importlib.util.spec_from_file_location('cleanup_orphans', _path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['cleanup_orphans'] = _mod
_spec.loader.exec_module(_mod)

find_orphans = _mod.find_orphans
delete_orphans = _mod.delete_orphans


def create_table(dynamodb):
    return dynamodb.create_table(
        TableName='applytic',
        KeySchema=[{'AttributeName': 'PK', 'KeyType': 'HASH'}, {'AttributeName': 'SK', 'KeyType': 'RANGE'}],
        AttributeDefinitions=[{'AttributeName': 'PK', 'AttributeType': 'S'}, {'AttributeName': 'SK', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST',
    )


def put_parent(table, user, app_id):
    table.put_item(Item={'PK': f'USER#{user}', 'SK': f'APP#{app_id}', 'appId': app_id, 'userId': user,
                         'entityType': 'APPLICATION'})


def put_children(table, user, app_id, with_user=True):
    for sk in ('EVENT#t1#a', 'NOTE#t2#b', 'CONTACT#t3#c'):
        item = {'PK': f'APP#{app_id}', 'SK': sk}
        if with_user:
            item['userId'] = user
        table.put_item(Item=item)


def child_count(table, app_id):
    return len(table.query(KeyConditionExpression=Key('PK').eq(f'APP#{app_id}'))['Items'])


class TestFindOrphans:

    def test_application_with_parent_is_not_an_orphan(self):
        with mock_aws():
            table = create_table(boto3.resource('dynamodb', region_name='us-east-1'))
            put_parent(table, 'u1', 'app-1')
            put_children(table, 'u1', 'app-1')
            result = find_orphans(table)
            assert result['orphans'] == {}
            assert result['partitions'] == 1

    def test_children_without_parent_are_orphans(self):
        with mock_aws():
            table = create_table(boto3.resource('dynamodb', region_name='us-east-1'))
            put_children(table, 'u1', 'gone')
            result = find_orphans(table)
            assert list(result['orphans']) == ['gone']
            assert result['orphans']['gone']['owner'] == 'u1'
            assert len(result['orphans']['gone']['keys']) == 3

    def test_partition_without_user_id_is_unresolvable_not_orphan(self):
        with mock_aws():
            table = create_table(boto3.resource('dynamodb', region_name='us-east-1'))
            put_children(table, 'u1', 'mystery', with_user=False)
            result = find_orphans(table)
            assert result['orphans'] == {}
            assert result['unresolvable'] == ['mystery']

    def test_user_filter_limits_the_report(self):
        with mock_aws():
            table = create_table(boto3.resource('dynamodb', region_name='us-east-1'))
            put_children(table, 'u1', 'gone-1')
            put_children(table, 'u2', 'gone-2')
            assert list(find_orphans(table, user_id='u1')['orphans']) == ['gone-1']

    def test_non_app_partitions_are_ignored(self):
        with mock_aws():
            table = create_table(boto3.resource('dynamodb', region_name='us-east-1'))
            table.put_item(Item={'PK': 'RATELIMIT#u1', 'SK': 'DATE#2024-01-01', 'count': 1})
            table.put_item(Item={'PK': 'USER#u1', 'SK': 'SETTINGS'})
            result = find_orphans(table)
            assert result['partitions'] == 0 and result['orphans'] == {}


class TestDeleteOrphans:

    def test_dry_run_style_find_deletes_nothing(self):
        with mock_aws():
            table = create_table(boto3.resource('dynamodb', region_name='us-east-1'))
            put_children(table, 'u1', 'gone')
            find_orphans(table)
            assert child_count(table, 'gone') == 3

    def test_apply_deletes_only_orphans(self):
        with mock_aws():
            table = create_table(boto3.resource('dynamodb', region_name='us-east-1'))
            put_parent(table, 'u1', 'live')
            put_children(table, 'u1', 'live')
            put_children(table, 'u1', 'gone')
            deleted = delete_orphans(table, find_orphans(table)['orphans'])
            assert deleted == 3
            assert child_count(table, 'gone') == 0
            assert child_count(table, 'live') == 3
            assert 'Item' in table.get_item(Key={'PK': 'USER#u1', 'SK': 'APP#live'})

    def test_unresolvable_partitions_survive_apply(self):
        with mock_aws():
            table = create_table(boto3.resource('dynamodb', region_name='us-east-1'))
            put_children(table, 'u1', 'mystery', with_user=False)
            delete_orphans(table, find_orphans(table)['orphans'])
            assert child_count(table, 'mystery') == 3