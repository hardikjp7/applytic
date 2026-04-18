import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as ses from 'aws-cdk-lib/aws-ses';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as cloudwatchActions from 'aws-cdk-lib/aws-cloudwatch-actions';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as snsSubscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import { Construct } from 'constructs';
import * as path from 'path';

export class ApplyticStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ─── DynamoDB — single table design ───────────────────────────────────────
    const table = new dynamodb.Table(this, 'ApplyticTable', {
      tableName: 'applytic',
      partitionKey: { name: 'PK', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'SK', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecovery: true,
      // v1.1: Enable TTL for rate limit record auto-cleanup
      // The 'ttl' attribute is already written by the rate limiter in insights Lambda
      timeToLiveAttribute: 'ttl',
    });

    // GSI: query all apps by user sorted by date
    table.addGlobalSecondaryIndex({
      indexName: 'GSI1',
      partitionKey: { name: 'GSI1PK', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'GSI1SK', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // ─── S3 — resume storage ──────────────────────────────────────────────────
    const resumeBucket = new s3.Bucket(this, 'ResumeBucket', {
      bucketName: `applytic-resumes-${this.account}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      lifecycleRules: [
        {
          noncurrentVersionExpiration: cdk.Duration.days(90),
        },
      ],
      cors: [
        {
          allowedMethods: [s3.HttpMethods.PUT, s3.HttpMethods.GET],
          allowedOrigins: ['*'], // tighten to your CloudFront domain in prod
          allowedHeaders: ['*'],
          maxAge: 3000,
        },
      ],
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ─── S3 — frontend static hosting ─────────────────────────────────────────
    const frontendBucket = new s3.Bucket(this, 'FrontendBucket', {
      bucketName: `applytic-frontend-${this.account}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    const distribution = new cloudfront.Distribution(this, 'FrontendCDN', {
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(frontendBucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },
      defaultRootObject: 'index.html',
      errorResponses: [
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html', // SPA fallback
        },
      ],
    });

    // v1.1: The CloudFront domain is used to tighten CORS below
    const cloudfrontDomain = `https://${distribution.distributionDomainName}`;

    // ─── Cognito ──────────────────────────────────────────────────────────────
    const userPool = new cognito.UserPool(this, 'UserPool', {
      userPoolName: 'applytic-users',
      selfSignUpEnabled: true,
      signInAliases: { email: true },
      autoVerify: { email: true },
      passwordPolicy: {
        minLength: 8,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: false,
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const userPoolClient = userPool.addClient('WebClient', {
      authFlows: {
        userPassword: true,
        userSrp: true,
      },
      oAuth: {
        flows: { implicitCodeGrant: true },
        scopes: [cognito.OAuthScope.EMAIL, cognito.OAuthScope.OPENID],
        callbackUrls: [cloudfrontDomain],
      },
    });

    // ─── Lambda shared config ─────────────────────────────────────────────────
    const commonEnv = {
      TABLE_NAME: table.tableName,
      RESUME_BUCKET: resumeBucket.bucketName,
      USER_POOL_ID: userPool.userPoolId,
      BEDROCK_MODEL_ID: 'amazon.nova-lite-v1:0',
      POWERTOOLS_SERVICE_NAME: 'applytic',
      LOG_LEVEL: 'INFO',
    };

    const runtime = lambda.Runtime.PYTHON_3_12;
    const architecture = lambda.Architecture.ARM_64;
    const logRetention = logs.RetentionDays.ONE_MONTH;

    // ─── Lambda: applications CRUD ────────────────────────────────────────────
    const applicationsLambda = new lambda.Function(this, 'ApplicationsLambda', {
      functionName: 'applytic-applications',
      runtime,
      architecture,
      memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      logRetention,
      environment: commonEnv,
      code: lambda.Code.fromAsset(
        path.join(__dirname, '../../lambdas/applications')
      ),
      handler: 'handler.lambda_handler',
      description: 'CRUD operations for job applications',
    });

    table.grantReadWriteData(applicationsLambda);
    resumeBucket.grantReadWrite(applicationsLambda);

    // ─── Lambda: insights + AI coaching ──────────────────────────────────────
    const insightsLambda = new lambda.Function(this, 'InsightsLambda', {
      functionName: 'applytic-insights',
      runtime,
      architecture,
      memorySize: 1024,
      timeout: cdk.Duration.seconds(60),
      logRetention,
      environment: commonEnv,
      code: lambda.Code.fromAsset(
        path.join(__dirname, '../../lambdas/insights')
      ),
      handler: 'handler.lambda_handler',
      description: 'Pattern analysis + Bedrock AI coaching',
    });

    table.grantReadData(insightsLambda);

    insightsLambda.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
        resources: ['*'],
      })
    );

    // ─── Lambda: weekly digest ────────────────────────────────────────────────
    const digestLambda = new lambda.Function(this, 'DigestLambda', {
      functionName: 'applytic-digest',
      runtime,
      architecture,
      memorySize: 512,
      timeout: cdk.Duration.seconds(120),
      logRetention,
      code: lambda.Code.fromAsset(
        path.join(__dirname, '../../lambdas/digest')
      ),
      handler: 'handler.lambda_handler',
      description: 'Weekly email digest via SES',
      environment: {
        ...commonEnv,
        SES_FROM_EMAIL: 'hardikjparmar7@gmail.com',
      },
    });

    table.grantReadData(digestLambda);
    digestLambda.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['ses:SendEmail', 'ses:SendRawEmail'],
        resources: ['*'],
      })
    );
    digestLambda.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['bedrock:InvokeModel'],
        resources: ['*'],
      })
    );
    digestLambda.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['cognito-idp:AdminGetUser'],
        resources: [userPool.userPoolArn],
      })
    );

    // ─── EventBridge: Monday 8am digest cron ──────────────────────────────────
    new events.Rule(this, 'WeeklyDigestRule', {
      ruleName: 'applytic-weekly-digest',
      description: 'Fires every Monday at 8am UTC',
      schedule: events.Schedule.cron({
        minute: '0',
        hour: '8',
        weekDay: 'MON',
      }),
      targets: [new targets.LambdaFunction(digestLambda)],
    });

    // ─── SNS topic for CloudWatch alarm notifications (v1.1) ─────────────────
    const alarmTopic = new sns.Topic(this, 'AlarmTopic', {
      topicName: 'applytic-alarms',
      displayName: 'Applytic CloudWatch Alarms',
    });

    // Subscribe your email to receive alarm notifications
    alarmTopic.addSubscription(
      new snsSubscriptions.EmailSubscription('hardikjparmar7@gmail.com')
    );

    // ─── CloudWatch alarms (v1.1) ─────────────────────────────────────────────

    // Applications Lambda — error rate alarm
    new cloudwatch.Alarm(this, 'ApplicationsLambdaErrorAlarm', {
      alarmName: 'applytic-applications-errors',
      alarmDescription: 'Applications Lambda error rate > 5 in 5 minutes',
      metric: applicationsLambda.metricErrors({
        period: cdk.Duration.minutes(5),
        statistic: 'Sum',
      }),
      threshold: 5,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    }).addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    // Insights Lambda — error rate alarm
    new cloudwatch.Alarm(this, 'InsightsLambdaErrorAlarm', {
      alarmName: 'applytic-insights-errors',
      alarmDescription: 'Insights Lambda error rate > 5 in 5 minutes',
      metric: insightsLambda.metricErrors({
        period: cdk.Duration.minutes(5),
        statistic: 'Sum',
      }),
      threshold: 5,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    }).addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    // Digest Lambda — error alarm (any error is noteworthy for a scheduled job)
    new cloudwatch.Alarm(this, 'DigestLambdaErrorAlarm', {
      alarmName: 'applytic-digest-errors',
      alarmDescription: 'Digest Lambda failed — weekly email may not have sent',
      metric: digestLambda.metricErrors({
        period: cdk.Duration.minutes(5),
        statistic: 'Sum',
      }),
      threshold: 1,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    }).addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    // Applications Lambda — p99 latency alarm
    new cloudwatch.Alarm(this, 'ApplicationsLambdaP99Alarm', {
      alarmName: 'applytic-applications-p99-latency',
      alarmDescription: 'Applications Lambda p99 latency > 10s',
      metric: applicationsLambda.metricDuration({
        period: cdk.Duration.minutes(5),
        statistic: 'p99',
      }),
      threshold: 10000, // milliseconds
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    }).addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    // Insights Lambda — p99 latency alarm (higher threshold — Bedrock calls are slow)
    new cloudwatch.Alarm(this, 'InsightsLambdaP99Alarm', {
      alarmName: 'applytic-insights-p99-latency',
      alarmDescription: 'Insights Lambda p99 latency > 30s (Bedrock timeout risk)',
      metric: insightsLambda.metricDuration({
        period: cdk.Duration.minutes(5),
        statistic: 'p99',
      }),
      threshold: 30000, // milliseconds
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    }).addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    // ─── API Gateway ──────────────────────────────────────────────────────────
    const api = new apigateway.RestApi(this, 'ApplyticApi', {
      restApiName: 'applytic-api',
      description: 'Job tracker REST API',
      // v1.1: CORS tightened to specific CloudFront domain instead of ALL_ORIGINS
      defaultCorsPreflightOptions: {
        allowOrigins: [
          cloudfrontDomain,
          'https://hardikjp7.github.io', // GitHub Pages origin
        ],
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'Authorization'],
        maxAge: cdk.Duration.hours(1),
      },
      deployOptions: {
        stageName: 'v1',
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: true,
        metricsEnabled: true,
      },
    });

    const cognitoAuthorizer = new apigateway.CognitoUserPoolsAuthorizer(
      this,
      'CognitoAuthorizer',
      {
        cognitoUserPools: [userPool],
        authorizerName: 'applytic-authorizer',
        identitySource: 'method.request.header.Authorization',
      }
    );

    const authOptions: apigateway.MethodOptions = {
      authorizer: cognitoAuthorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    };

    // /applications
    const appsResource = api.root.addResource('applications');
    appsResource.addMethod(
      'GET',
      new apigateway.LambdaIntegration(applicationsLambda),
      authOptions
    );
    appsResource.addMethod(
      'POST',
      new apigateway.LambdaIntegration(applicationsLambda),
      authOptions
    );

    // /applications/{appId}
    const appResource = appsResource.addResource('{appId}');
    appResource.addMethod(
      'GET',
      new apigateway.LambdaIntegration(applicationsLambda),
      authOptions
    );
    appResource.addMethod(
      'PUT',
      new apigateway.LambdaIntegration(applicationsLambda),
      authOptions
    );
    appResource.addMethod(
      'DELETE',
      new apigateway.LambdaIntegration(applicationsLambda),
      authOptions
    );

    // /applications/{appId}/status
    const statusResource = appResource.addResource('status');
    statusResource.addMethod(
      'POST',
      new apigateway.LambdaIntegration(applicationsLambda),
      authOptions
    );

    // /insights
    const insightsResource = api.root.addResource('insights');
    insightsResource.addMethod(
      'GET',
      new apigateway.LambdaIntegration(insightsLambda),
      authOptions
    );

    // /insights/chat
    const chatResource = insightsResource.addResource('chat');
    chatResource.addMethod(
      'POST',
      new apigateway.LambdaIntegration(insightsLambda),
      authOptions
    );

    // /resumes/upload-url
    const resumesResource = api.root.addResource('resumes');
    const uploadUrlResource = resumesResource.addResource('upload-url');
    uploadUrlResource.addMethod(
      'POST',
      new apigateway.LambdaIntegration(applicationsLambda),
      authOptions
    );

    // /resumes/list
    const listResumesResource = resumesResource.addResource('list');
    listResumesResource.addMethod(
      'GET',
      new apigateway.LambdaIntegration(applicationsLambda),
      authOptions
    );

    // ─── Outputs ──────────────────────────────────────────────────────────────
    new cdk.CfnOutput(this, 'ApiUrl', {
      value: api.url,
      description: 'REST API base URL',
    });
    new cdk.CfnOutput(this, 'FrontendUrl', {
      value: cloudfrontDomain,
      description: 'CloudFront frontend URL',
    });
    new cdk.CfnOutput(this, 'UserPoolId', {
      value: userPool.userPoolId,
    });
    new cdk.CfnOutput(this, 'UserPoolClientId', {
      value: userPoolClient.userPoolClientId,
    });
    new cdk.CfnOutput(this, 'ResumeBucketName', {
      value: resumeBucket.bucketName,
    });
    new cdk.CfnOutput(this, 'AlarmTopicArn', {
      value: alarmTopic.topicArn,
      description: 'SNS topic ARN for CloudWatch alarm notifications',
    });
  }
}
