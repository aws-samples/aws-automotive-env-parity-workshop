# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

import aws_cdk.aws_codebuild as codebuild
import aws_cdk.aws_codecommit as codecommit
import aws_cdk.aws_codepipeline as codepipeline
import aws_cdk.aws_codepipeline_actions as codepipeline_actions
import aws_cdk.aws_ecr as ecr
import aws_cdk.aws_iam as iam
import aws_cdk.core
from aws_cdk import core


class CdkPipelineStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        name = "arm-devsummit"

        # ECR repositories
        container_repository = ecr.Repository(
            scope=self,
            id=f"{name}-container",
            repository_name=f"{name}"
        )

        container_repository.apply_removal_policy(aws_cdk.core.RemovalPolicy.DESTROY)

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
        pipeline.add_stage(
            stage_name="DockerBuild",
            actions=[
                codepipeline_actions.CodeBuildAction(
                    action_name=f"DockerBuild_ARM64",
                    project=docker_build_arm64,
                    input=source_output,
                    outputs=[docker_output_arm64])
            ]
        )

        # Outputs
        core.CfnOutput(
            scope=self,
            id="application_repository",
            value=codecommit_repo.repository_clone_url_http
        )
