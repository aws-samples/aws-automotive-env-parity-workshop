# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

import aws_cdk.core as core
import aws_cdk.aws_codebuild as codebuild
import aws_cdk.aws_codecommit as codecommit
import aws_cdk.aws_codepipeline as codepipeline
import aws_cdk.aws_codepipeline_actions as codepipeline_actions
import aws_cdk.aws_ecr as ecr
import aws_cdk.aws_iam as iam
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_cloudtrail as cloudtrail
import aws_cdk.aws_batch as batch
import aws_cdk.aws_lambda as aws_lambda

user_data = '''MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="==MYBOUNDARY=="

--==MYBOUNDARY==
Content-Type: text/x-shellscript; charset="us-ascii"

#!/bin/sh
mkdir -p /var/log/ecs /etc/ecs /var/lib/ecs/data /etc/ecs/ && touch /etc/ecs/ecs.config
sysctl -w net.ipv4.conf.all.route_localnet=1
iptables -t nat -A PREROUTING -p tcp -d 169.254.170.2 --dport 80 -j DNAT --to-destination 127.0.0.1:51679
iptables -t nat -A OUTPUT -d 169.254.170.2 -p tcp -m tcp --dport 80 -j REDIRECT --to-ports 51679
docker run --name ecs-agent \
--detach=true \
--restart=on-failure:10 \
--volume=/var/run/docker.sock:/var/run/docker.sock \
--volume=/var/log/ecs:/log \
--volume=/var/lib/ecs/data:/data \
--env-file=/etc/ecs/ecs.config \
--net=host \
--env=ECS_LOGFILE=/log/ecs-agent.log \
--env=ECS_DATADIR=/data/ \
--env=ECS_AVAILABLE_LOGGING_DRIVERS='[\"json-file\",\"awslogs\"]' \
--env=ECS_ENABLE_TASK_IAM_ROLE=true \
--env=ECS_DISABLE_IMAGE_CLEANUP=false \
--env=ECS_ENGINE_TASK_CLEANUP_WAIT_DURATION=2m \
--env=ECS_IMAGE_CLEANUP_INTERVAL=10m \
--env=ECS_IMAGE_MINIMUM_CLEANUP_AGE=10m \
--env=ECS_NUM_IMAGES_DELETE_PER_CYCLE=5 \
--env=ECS_RESERVED_MEMORY=32 \
--env=ECS_IMAGE_CLEANUP_INTERVAL=60m \
--env=ECS_IMAGE_MINIMUM_CLEANUP_AGE=60m \
--env=ECS_ENABLE_TASK_IAM_ROLE_NETWORK_HOST=true amazon/amazon-ecs-agent:latest

--==MYBOUNDARY==--'''

class CdkBatchStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        name = "yolo-application-batch"
        
        bucket = s3.Bucket(self, name)
        bucket.apply_removal_policy(core.RemovalPolicy.DESTROY)
        
        ecs_ami = ecs.EcsOptimizedAmi(generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2,
                                                             hardware_type=ecs.AmiHardwareType.ARM)
                                                             
        ecs_yocto_ami = ec2.GenericLinuxImage({
          'eu-west-1': 'ami-0f582a3d84fdd665f',
          'us-east-1': 'ami-0a84ddb8204ac5721'
        });
    
        # ECR repositories
        container_repository = ecr.Repository(
            scope=self,
            id=f"{name}-container",
            repository_name=f"{name}"
        )

        container_repository.apply_removal_policy(core.RemovalPolicy.DESTROY)

        # Repo for Application
        codecommit_repo = codecommit.Repository(
            scope=self,
            id=f"{name}-container-git",
            repository_name=f"{name}",
            description=f"Application code"
        )

        # pipeline definition
        pipeline = codepipeline.Pipeline(
            scope=self,
            id=f"{name}-container-pipeline",
            pipeline_name=f"{name}-pipeline"
        )

        source_output = codepipeline.Artifact()
        docker_output_arm64 = codepipeline.Artifact("ARM64_BuildOutput")

        # codebuild resources
        docker_build_arm64 = codebuild.PipelineProject(
            scope=self,
            id=f"DockerBuild_ARM64",
            environment=dict(build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_ARM, privileged=True),
            environment_variables={
                'REPO_ECR': codebuild.BuildEnvironmentVariable(value=container_repository.repository_uri)
            },

            build_spec=codebuild.BuildSpec.from_source_filename("buildspec.yml")
        )

        container_repository.grant_pull_push(docker_build_arm64)

        docker_build_arm64.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage"],
            resources=[
                f"arn:{core.Stack.of(self).partition}:ecr:{core.Stack.of(self).region}:{core.Stack.of(self).account}:repository/*"],
        )
        )

        source_action = codepipeline_actions.CodeCommitSourceAction(
            action_name="CodeCommit_Source",
            repository=codecommit_repo,
            output=source_output,
            branch="master"
        )

        # Stages in CodePipeline
        # source stage (clone codecommit repo)
        pipeline.add_stage(stage_name="Source", actions=[source_action])

        # build stage (build image from Dockerfile and push to ECR)
        build = pipeline.add_stage(
            stage_name="DockerBuild",
            actions=[
                codepipeline_actions.CodeBuildAction(
                    action_name=f"DockerBuild_ARM64",
                    project=docker_build_arm64,
                    input=source_output,
                    outputs=[docker_output_arm64],
                    environment_variables={
                        "HELLO": {
                            "value": "WORLD"
                        }
                    }
                )
            ]
        )

        my_launch_template = ec2.CfnLaunchTemplate(self, "MyLaunchTemplate",
            launch_template_name="MyLaunchTemplate",
            launch_template_data={
                "userData": core.Fn.base64(user_data)
            }
        )
        
        spot_environment = batch.ComputeEnvironment(self, "MySpotEnvironment",
            compute_resources={
                "type": batch.ComputeResourceType.SPOT,
                "bid_percentage": 80, # Bids for resources at 80% of the on-demand price
                "vpc": vpc,
                "image": ecs_yocto_ami,
                "launch_template": {
                    "launch_template_name": my_launch_template.launch_template_name
                },
                "instance_types": [
                    # All the supported Graviton2 batch instance types
                    ec2.InstanceType("m6g.xlarge"),
                    ec2.InstanceType("m6g.2xlarge"),
                    ec2.InstanceType("m6g.4xlarge"),
                    ec2.InstanceType("m6g.8xlarge"),
                    ec2.InstanceType("m6g.12xlarge"),
                    ec2.InstanceType("m6g.16xlarge"),
                    ec2.InstanceType("c6g.xlarge"),
                    ec2.InstanceType("c6g.2xlarge"),
                    ec2.InstanceType("c6g.4xlarge"),
                    ec2.InstanceType("c6g.8xlarge"),
                    ec2.InstanceType("c6g.12xlarge"),
                    ec2.InstanceType("c6g.16xlarge")
                ]
            }
        )
        
        job_queue = batch.JobQueue(self, "MyJobQueue",
            compute_environments=[
                batch.JobQueueComputeEnvironment(
                    # Defines a collection of compute resources to handle assigned batch jobs
                    compute_environment=spot_environment,
                    order=1
                )
            ]
        )
        
        job_def = batch.JobDefinition(self, "batch-job-def-from-ecr",
            container={
                "image": ecs.ContainerImage.from_registry(container_repository.repository_uri)
            }
        )
        
        # Batch - ComputeEnvironment - Job Queue - Job Definition
        lambda_role = iam.Role(self, "MyBatchExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("AWSLambdaExecute"),
                              iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"),
                              iam.ManagedPolicy.from_aws_managed_policy_name("AWSXRayDaemonWriteAccess"),
                              iam.ManagedPolicy.from_aws_managed_policy_name("AWSBatchFullAccess")
                              ]
        )
        
                # Lambda dynamo event trigger
        batch_lambda = aws_lambda.Function(self, "BatchSubmit",
            runtime=aws_lambda.Runtime.PYTHON_3_8,
            handler="lambda.lambda_handler",
            code=aws_lambda.Code.asset("./cdk/batch_pipeline/lambda"),
            role=lambda_role,
            tracing=aws_lambda.Tracing.ACTIVE,
            environment={
                "S3_BUCKET": bucket.bucket_name
            }
        )
        
        batch_lambda.add_environment("BATCH_JOB_NAME", 'MyBatchJob')
        batch_lambda.add_environment("BATCH_JOB_QUEUE", job_queue.job_queue_name)
        batch_lambda.add_environment("BATCH_JOB_DEFINITION", job_def.job_definition_name)
        
        lambda_action = codepipeline_actions.LambdaInvokeAction(
            action_name="Lambda",
            lambda_=batch_lambda
        )
        pipeline.add_stage(
            stage_name="SubmitBatchLambda",
            actions=[lambda_action]
        )
        
        batch_lambda.grant_invoke(pipeline.role)

        # Outputs
        core.CfnOutput(
            scope=self,
            id="application_repository",
            value=codecommit_repo.repository_clone_url_http
        )
        
        core.CfnOutput(
            scope=self,
            id="bucket",
            value=bucket.bucket_name
        )
