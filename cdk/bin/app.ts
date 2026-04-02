#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { ApplyticStack } from '../lib/applytic-stack';

const app = new cdk.App();

new ApplyticStack(app, 'ApplyticStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION ?? 'us-east-1',
  },
  tags: {
    project: 'applytic',
    owner: 'kashyap',
  },
});
