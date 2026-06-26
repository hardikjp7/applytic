import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as cloudwatchActions from 'aws-cdk-lib/aws-cloudwatch-actions';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as snsSubscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager'; // v2.3
import { Construct } from 'constructs';
import * as path from 'path';

export class ApplyticStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ─── DynamoDB ─────────────────────────────────────────────────────────────
    const table = new dynamodb.Table(this, 'ApplyticTable', {
      tableName: 'applytic',
      partitionKey: { name: 'PK', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'SK', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecovery: true,
      timeToLiveAttribute: 'ttl',
    });

    table.addGlobalSecondaryIndex({
      indexName: 'GSI1',
      partitionKey: { name: 'GSI1PK', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'GSI1SK', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // ─── S3 - resumes ─────────────────────────────────────────────────────────
    const resumeBucket = new s3.Bucket(this, 'ResumeBucket', {
      bucketName: `applytic-resumes-${this.account}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      lifecycleRules: [{ noncurrentVersionExpiration: cdk.Duration.days(90) }],
      cors: [{ allowedMethods: [s3.HttpMethods.PUT, s3.HttpMethods.GET], allowedOrigins: ['*'], allowedHeaders: ['*'], maxAge: 3000 }],
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ─── S3 - frontend ────────────────────────────────────────────────────────
    const frontendBucket = new s3.Bucket(this, 'FrontendBucket', {
      bucketName: `applytic-frontend-${this.account}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // ─── v2.2: cache policy for API docs ──────────────────────────────────────
    const apiDocsCachePolicy = new cloudfront.CachePolicy(this, 'ApiDocsCachePolicy', {
      cachePolicyName: 'applytic-api-docs',
      defaultTtl: cdk.Duration.minutes(5),
      minTtl: cdk.Duration.seconds(0),
      maxTtl: cdk.Duration.hours(1),
    });

    const frontendOrigin = origins.S3BucketOrigin.withOriginAccessControl(frontendBucket);

    const distribution = new cloudfront.Distribution(this, 'FrontendCDN', {
      defaultBehavior: {
        origin: frontendOrigin,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },
      additionalBehaviors: {
        'api/docs/*': {
          origin: frontendOrigin,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          cachePolicy: apiDocsCachePolicy,
        },
      },
      defaultRootObject: 'index.html',
      errorResponses: [{ httpStatus: 404, responseHttpStatus: 200, responsePagePath: '/index.html' }],
    });

    const cloudfrontDomain = `https://${distribution.distributionDomainName}`;
    const customDomain = 'https://hardikjp7.com';
    const customDomainApplytic = 'https://hardikjp7.com/applytic';

    // ─── Cognito ──────────────────────────────────────────────────────────────
    const userPool = new cognito.UserPool(this, 'UserPool', {
      userPoolName: 'applytic-users',
      selfSignUpEnabled: true,
      signInAliases: { email: true },
      autoVerify: { email: true },
      passwordPolicy: { minLength: 8, requireUppercase: true, requireDigits: true, requireSymbols: false },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ─── v2.3: Google OAuth credentials from Secrets Manager ──────────────────
    // Secret was pre-created via:
    //   aws secretsmanager create-secret --name applytic/google-oauth \
    //     --secret-string '{"client_id":"...","client_secret":"..."}'
    // Never commit credentials - always read from Secrets Manager at deploy time.
    const googleOAuthSecret = secretsmanager.Secret.fromSecretNameV2(
      this, 'GoogleOAuthSecret', 'applytic/google-oauth'
    );

    // ─── v2.3: Google Identity Provider ───────────────────────────────────────
    // client_id is not truly secret (appears in OAuth redirect URLs) so
    // unsafeUnwrap() is the accepted CDK pattern here.
    // client_secret is passed as SecretValue and never appears in plain text.
    const googleProvider = new cognito.UserPoolIdentityProviderGoogle(this, 'GoogleProvider', {
      userPool,
      clientId: googleOAuthSecret.secretValueFromJson('client_id').unsafeUnwrap(),
      clientSecretValue: googleOAuthSecret.secretValueFromJson('client_secret'),
      scopes: ['email', 'profile', 'openid'],
      attributeMapping: {
        email: cognito.ProviderAttribute.GOOGLE_EMAIL,
        givenName: cognito.ProviderAttribute.GOOGLE_GIVEN_NAME,
        familyName: cognito.ProviderAttribute.GOOGLE_FAMILY_NAME,
      },
    });

    // ─── v2.3: Hosted UI domain ────────────────────────────────────────────────
    // Full domain: applytic-auth.auth.us-east-1.amazoncognito.com
    // Required for OAuth redirect flow (Google sign-in).
    const hostedUiDomain = userPool.addDomain('HostedUiDomain', {
      cognitoDomain: {
        domainPrefix: 'applytic-auth',
      },
    });

    // ─── v2.3: UserPoolClient - updated from v2.2 ─────────────────────────────
    // Changes vs previous:
    //   - implicitCodeGrant -> authorizationCodeGrant (more secure, required for PKCE)
    //   - Added PROFILE scope (needed for Google name attributes)
    //   - Added /auth/callback URLs for the new OAuth redirect route
    //   - Added logoutUrls
    //   - Added GOOGLE to supportedIdentityProviders
    // The old root callback URLs are kept during transition and will be removed
    // in Session 2 once the frontend no longer needs them.
    const userPoolClient = userPool.addClient('WebClient', {
      authFlows: { userPassword: true, userSrp: true },
      oAuth: {
        flows: { authorizationCodeGrant: true },
        scopes: [
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.PROFILE,
        ],
        callbackUrls: [
          // v2.3: primary OAuth redirect target for all deployments
          `${cloudfrontDomain}/auth/callback`,
          'https://hardikjp7.github.io/applytic/auth/callback',
          `${customDomainApplytic}/auth/callback`,
          // kept for backward compat during Session 2 transition
          cloudfrontDomain,
          'https://hardikjp7.github.io/applytic',
          customDomain,
          customDomainApplytic,
        ],
        logoutUrls: [
          `${cloudfrontDomain}/`,
          'https://hardikjp7.github.io/applytic/',
          `${customDomainApplytic}/`,
        ],
      },
      supportedIdentityProviders: [
        cognito.UserPoolClientIdentityProvider.COGNITO,
        cognito.UserPoolClientIdentityProvider.GOOGLE,
      ],
    });

    // Google provider must exist before the client references it
    userPoolClient.node.addDependency(googleProvider);

    // ─── v1.2: Shared Lambda Layer ────────────────────────────────────────────
    const sharedLayer = new lambda.LayerVersion(this, 'SharedLayer', {
      layerVersionName: 'applytic-shared',
      description: 'Shared middleware, Pydantic, X-Ray SDK, Powertools',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/shared_layer')),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_12],
      compatibleArchitectures: [lambda.Architecture.ARM_64],
    });

    // ─── Lambda shared config ─────────────────────────────────────────────────
    const commonEnv = {
      TABLE_NAME: table.tableName,
      RESUME_BUCKET: resumeBucket.bucketName,
      USER_POOL_ID: userPool.userPoolId,
      BEDROCK_MODEL_ID: 'amazon.nova-lite-v1:0',
      POWERTOOLS_SERVICE_NAME: 'applytic',
      LOG_LEVEL: 'INFO',
      AWS_XRAY_TRACING_NAME: 'applytic',
    };

    const runtime = lambda.Runtime.PYTHON_3_12;
    const architecture = lambda.Architecture.ARM_64;
    const logRetention = logs.RetentionDays.ONE_MONTH;
    const tracingConfig = lambda.Tracing.ACTIVE;

    // ─── Lambda: applications ─────────────────────────────────────────────────
    const applicationsLambda = new lambda.Function(this, 'ApplicationsLambda', {
      functionName: 'applytic-applications',
      runtime, architecture, memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      logRetention, tracing: tracingConfig,
      environment: commonEnv, layers: [sharedLayer],
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/applications')),
      handler: 'handler.lambda_handler',
      description: 'CRUD operations for job applications',
    });

    table.grantReadWriteData(applicationsLambda);
    resumeBucket.grantReadWrite(applicationsLambda);

    // ─── Lambda: insights ─────────────────────────────────────────────────────
    const insightsLambda = new lambda.Function(this, 'InsightsLambda', {
      functionName: 'applytic-insights',
      runtime, architecture, memorySize: 1024,
      timeout: cdk.Duration.seconds(60),
      logRetention, tracing: tracingConfig,
      environment: commonEnv, layers: [sharedLayer],
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/insights')),
      handler: 'handler.lambda_handler',
      description: 'Pattern analysis + Bedrock AI coaching',
    });

    table.grantReadData(insightsLambda);
    insightsLambda.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
      resources: ['*'],
    }));

    // ─── Lambda: digest ───────────────────────────────────────────────────────
    const digestLambda = new lambda.Function(this, 'DigestLambda', {
      functionName: 'applytic-digest',
      runtime, architecture, memorySize: 512,
      timeout: cdk.Duration.seconds(120),
      logRetention, tracing: tracingConfig, layers: [sharedLayer],
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/digest')),
      handler: 'handler.lambda_handler',
      description: 'Weekly email digest via SES',
      environment: { ...commonEnv, SES_FROM_EMAIL: 'hardikjparmar7@gmail.com' },
    });

    table.grantReadData(digestLambda);
    digestLambda.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['ses:SendEmail', 'ses:SendRawEmail', 'bedrock:InvokeModel'],
      resources: ['*'],
    }));
    digestLambda.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['cognito-idp:AdminGetUser'],
      resources: [userPool.userPoolArn],
    }));

    // ─── v1.2: Lambda: Cognito Post Confirmation - SES verify ─────────────────
    const cognitoVerifyLambda = new lambda.Function(this, 'CognitoVerifyLambda', {
      functionName: 'applytic-cognito-verify',
      runtime, architecture, memorySize: 256,
      timeout: cdk.Duration.seconds(10),
      logRetention, tracing: tracingConfig, layers: [sharedLayer],
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/cognito_verify')),
      handler: 'handler.lambda_handler',
      description: 'Auto-verifies new user emails in SES on Cognito signup',
      environment: { POWERTOOLS_SERVICE_NAME: 'applytic', LOG_LEVEL: 'INFO' },
    });

    cognitoVerifyLambda.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['ses:VerifyEmailIdentity', 'ses:GetIdentityVerificationAttributes'],
      resources: ['*'],
    }));

    // Post Confirmation: fires when a native email/password user confirms their account
    userPool.addTrigger(cognito.UserPoolOperation.POST_CONFIRMATION, cognitoVerifyLambda);

    // v2.3: Post Authentication: fires on every successful sign-in, native or federated.
    // This ensures Google sign-in users also get their email SES-verified so they
    // receive the Monday digest. The Lambda's existing idempotency check
    // (VerificationStatus == 'Success' -> skip) makes repeated calls safe - it's
    // a no-op after the first successful SES verification. No Lambda code changes needed.
    userPool.addTrigger(cognito.UserPoolOperation.POST_AUTHENTICATION, cognitoVerifyLambda);

    // ─── v2.0: Lambda: follow-up reminders ───────────────────────────────────
    const followUpLambda = new lambda.Function(this, 'FollowUpLambda', {
      functionName: 'applytic-followup',
      runtime, architecture, memorySize: 512,
      timeout: cdk.Duration.seconds(120),
      logRetention, tracing: tracingConfig, layers: [sharedLayer],
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/followup')),
      handler: 'handler.lambda_handler',
      description: 'v2.0 - Daily follow-up reminder emails for overdue applications',
      environment: { ...commonEnv, SES_FROM_EMAIL: 'hardikjparmar7@gmail.com' },
    });

    table.grantReadData(followUpLambda);
    followUpLambda.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['ses:SendEmail', 'ses:SendRawEmail'],
      resources: ['*'],
    }));
    followUpLambda.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['cognito-idp:AdminGetUser'],
      resources: [userPool.userPoolArn],
    }));

    // ─── v2.0: Lambda: user settings ─────────────────────────────────────────
    const settingsLambda = new lambda.Function(this, 'SettingsLambda', {
      functionName: 'applytic-settings',
      runtime, architecture, memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      logRetention, tracing: tracingConfig, layers: [sharedLayer],
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/settings')),
      handler: 'handler.lambda_handler',
      description: 'v2.0 - User settings: weekly goal and streak tracking',
      environment: commonEnv,
    });

    table.grantReadWriteData(settingsLambda);

    // ─── v2.0: Lambda: notes timeline ────────────────────────────────────────
    const notesLambda = new lambda.Function(this, 'NotesLambda', {
      functionName: 'applytic-notes',
      runtime, architecture, memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      logRetention, tracing: tracingConfig, layers: [sharedLayer],
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/notes')),
      handler: 'handler.lambda_handler',
      description: 'v2.0 - Timestamped notes timeline per application',
      environment: commonEnv,
    });

    table.grantReadWriteData(notesLambda);

    // ─── v1.2 + v2.0: X-Ray IAM for all Lambdas ──────────────────────────────
    const xrayPolicy = new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['xray:PutTraceSegments', 'xray:PutTelemetryRecords', 'xray:GetSamplingRules', 'xray:GetSamplingTargets'],
      resources: ['*'],
    });

    [
      applicationsLambda, insightsLambda, digestLambda,
      cognitoVerifyLambda, followUpLambda, settingsLambda, notesLambda,
    ].forEach(fn => fn.addToRolePolicy(xrayPolicy));

    // ─── EventBridge: Monday 8am UTC - weekly digest ──────────────────────────
    new events.Rule(this, 'WeeklyDigestRule', {
      ruleName: 'applytic-weekly-digest',
      description: 'Fires every Monday at 8am UTC',
      schedule: events.Schedule.cron({ minute: '0', hour: '8', weekDay: 'MON' }),
      targets: [new targets.LambdaFunction(digestLambda)],
    });

    // ─── v2.0: EventBridge: daily 9am UTC - follow-up reminders ──────────────
    new events.Rule(this, 'DailyFollowUpRule', {
      ruleName: 'applytic-daily-followup',
      description: 'v2.0 - Fires every day at 9am UTC to send follow-up reminders',
      schedule: events.Schedule.cron({ minute: '0', hour: '9' }),
      targets: [new targets.LambdaFunction(followUpLambda)],
    });

    // ─── SNS alarms topic ─────────────────────────────────────────────────────
    const alarmTopic = new sns.Topic(this, 'AlarmTopic', {
      topicName: 'applytic-alarms',
      displayName: 'Applytic CloudWatch Alarms',
    });
    alarmTopic.addSubscription(new snsSubscriptions.EmailSubscription('hardikjparmar7@gmail.com'));

    // ─── CloudWatch alarms ────────────────────────────────────────────────────
    const alarmDefaults = {
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    };

    new cloudwatch.Alarm(this, 'ApplicationsLambdaErrorAlarm', {
      alarmName: 'applytic-applications-errors',
      metric: applicationsLambda.metricErrors({ period: cdk.Duration.minutes(5), statistic: 'Sum' }),
      threshold: 5, ...alarmDefaults,
    }).addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    new cloudwatch.Alarm(this, 'InsightsLambdaErrorAlarm', {
      alarmName: 'applytic-insights-errors',
      metric: insightsLambda.metricErrors({ period: cdk.Duration.minutes(5), statistic: 'Sum' }),
      threshold: 5, ...alarmDefaults,
    }).addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    new cloudwatch.Alarm(this, 'DigestLambdaErrorAlarm', {
      alarmName: 'applytic-digest-errors',
      metric: digestLambda.metricErrors({ period: cdk.Duration.minutes(5), statistic: 'Sum' }),
      threshold: 1, ...alarmDefaults,
    }).addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    new cloudwatch.Alarm(this, 'FollowUpLambdaErrorAlarm', {
      alarmName: 'applytic-followup-errors',
      metric: followUpLambda.metricErrors({ period: cdk.Duration.minutes(5), statistic: 'Sum' }),
      threshold: 1, ...alarmDefaults,
    }).addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    new cloudwatch.Alarm(this, 'ApplicationsLambdaP99Alarm', {
      alarmName: 'applytic-applications-p99-latency',
      metric: applicationsLambda.metricDuration({ period: cdk.Duration.minutes(5), statistic: 'p99' }),
      threshold: 10000, evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    }).addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    new cloudwatch.Alarm(this, 'InsightsLambdaP99Alarm', {
      alarmName: 'applytic-insights-p99-latency',
      metric: insightsLambda.metricDuration({ period: cdk.Duration.minutes(5), statistic: 'p99' }),
      threshold: 30000, evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    }).addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    // ─── CloudWatch Dashboard ─────────────────────────────────────────────────
    new cloudwatch.Dashboard(this, 'ApplyticDashboard', {
      dashboardName: 'applytic-overview',
      widgets: [
        [
          new cloudwatch.GraphWidget({
            title: 'Lambda Invocations',
            left: [
              applicationsLambda.metricInvocations({ period: cdk.Duration.minutes(5) }),
              insightsLambda.metricInvocations({ period: cdk.Duration.minutes(5) }),
              digestLambda.metricInvocations({ period: cdk.Duration.minutes(5) }),
              followUpLambda.metricInvocations({ period: cdk.Duration.minutes(5) }),
              settingsLambda.metricInvocations({ period: cdk.Duration.minutes(5) }),
              notesLambda.metricInvocations({ period: cdk.Duration.minutes(5) }),
            ],
            width: 12,
          }),
          new cloudwatch.GraphWidget({
            title: 'Lambda Errors',
            left: [
              applicationsLambda.metricErrors({ period: cdk.Duration.minutes(5) }),
              insightsLambda.metricErrors({ period: cdk.Duration.minutes(5) }),
              digestLambda.metricErrors({ period: cdk.Duration.minutes(5) }),
              followUpLambda.metricErrors({ period: cdk.Duration.minutes(5) }),
              settingsLambda.metricErrors({ period: cdk.Duration.minutes(5) }),
              notesLambda.metricErrors({ period: cdk.Duration.minutes(5) }),
            ],
            width: 12,
          }),
        ],
        [
          new cloudwatch.GraphWidget({
            title: 'Lambda Duration p99',
            left: [
              applicationsLambda.metricDuration({ period: cdk.Duration.minutes(5), statistic: 'p99' }),
              insightsLambda.metricDuration({ period: cdk.Duration.minutes(5), statistic: 'p99' }),
            ],
            width: 12,
          }),
          new cloudwatch.GraphWidget({
            title: 'Lambda Throttles',
            left: [
              applicationsLambda.metricThrottles({ period: cdk.Duration.minutes(5) }),
              insightsLambda.metricThrottles({ period: cdk.Duration.minutes(5) }),
            ],
            width: 12,
          }),
        ],
      ],
    });

    // ─── API Gateway ──────────────────────────────────────────────────────────
    const api = new apigateway.RestApi(this, 'ApplyticApi', {
      restApiName: 'applytic-api',
      description: 'Job tracker REST API',
      defaultCorsPreflightOptions: {
        allowOrigins: [
          cloudfrontDomain,
          'https://hardikjp7.github.io',
          customDomain,
          customDomainApplytic,
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
        tracingEnabled: true,
      },
    });

    const cognitoAuthorizer = new apigateway.CognitoUserPoolsAuthorizer(this, 'CognitoAuthorizer', {
      cognitoUserPools: [userPool],
      authorizerName: 'applytic-authorizer',
      identitySource: 'method.request.header.Authorization',
    });

    const authOptions: apigateway.MethodOptions = {
      authorizer: cognitoAuthorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    };

    // ─── existing routes ──────────────────────────────────────────────────────
    const appsResource = api.root.addResource('applications');
    appsResource.addMethod('GET', new apigateway.LambdaIntegration(applicationsLambda), authOptions);
    appsResource.addMethod('POST', new apigateway.LambdaIntegration(applicationsLambda), authOptions);

    const appResource = appsResource.addResource('{appId}');
    appResource.addMethod('GET', new apigateway.LambdaIntegration(applicationsLambda), authOptions);
    appResource.addMethod('PUT', new apigateway.LambdaIntegration(applicationsLambda), authOptions);
    appResource.addMethod('DELETE', new apigateway.LambdaIntegration(applicationsLambda), authOptions);
    appResource.addResource('status').addMethod('POST', new apigateway.LambdaIntegration(applicationsLambda), authOptions);

    const insightsResource = api.root.addResource('insights');
    insightsResource.addMethod('GET', new apigateway.LambdaIntegration(insightsLambda), authOptions);
    insightsResource.addResource('chat').addMethod('POST', new apigateway.LambdaIntegration(insightsLambda), authOptions);

    const resumesResource = api.root.addResource('resumes');
    resumesResource.addResource('upload-url').addMethod('POST', new apigateway.LambdaIntegration(applicationsLambda), authOptions);
    resumesResource.addResource('list').addMethod('GET', new apigateway.LambdaIntegration(applicationsLambda), authOptions);

    // ─── v2.0: /users/settings ────────────────────────────────────────────────
    const usersResource = api.root.addResource('users');
    const settingsResource = usersResource.addResource('settings');
    settingsResource.addMethod('GET', new apigateway.LambdaIntegration(settingsLambda), authOptions);
    settingsResource.addMethod('PUT', new apigateway.LambdaIntegration(settingsLambda), authOptions);

    // ─── v2.0: /applications/{appId}/notes routes ─────────────────────────────
    const notesResource = appResource.addResource('notes');
    notesResource.addMethod('GET', new apigateway.LambdaIntegration(notesLambda), authOptions);
    notesResource.addMethod('POST', new apigateway.LambdaIntegration(notesLambda), authOptions);

    const noteResource = notesResource.addResource('{noteId}');
    noteResource.addMethod('DELETE', new apigateway.LambdaIntegration(notesLambda), authOptions);

    // ─── Outputs ──────────────────────────────────────────────────────────────
    new cdk.CfnOutput(this, 'ApiUrl', { value: api.url, description: 'REST API base URL' });
    new cdk.CfnOutput(this, 'FrontendUrl', { value: cloudfrontDomain });
    new cdk.CfnOutput(this, 'UserPoolId', { value: userPool.userPoolId });
    new cdk.CfnOutput(this, 'UserPoolClientId', { value: userPoolClient.userPoolClientId });
    new cdk.CfnOutput(this, 'ResumeBucketName', { value: resumeBucket.bucketName });
    new cdk.CfnOutput(this, 'AlarmTopicArn', { value: alarmTopic.topicArn });
    new cdk.CfnOutput(this, 'SharedLayerArn', { value: sharedLayer.layerVersionArn });
    new cdk.CfnOutput(this, 'ApiDocsUrl', { value: `${cloudfrontDomain}/api/docs/`, description: 'Swagger UI - API reference' });

    // ─── v2.3: new outputs ────────────────────────────────────────────────────
    new cdk.CfnOutput(this, 'HostedUiBaseUrl', {
      value: `https://applytic-auth.auth.${this.region}.amazoncognito.com`,
      description: 'v2.3 - Cognito Hosted UI base URL (used in Amplify oauth config)',
    });
    new cdk.CfnOutput(this, 'GoogleIdpRedirectUri', {
      value: `https://applytic-auth.auth.${this.region}.amazoncognito.com/oauth2/idpresponse`,
      description: 'v2.3 - Add this as an Authorized Redirect URI in Google Cloud Console',
    });
  }
}
