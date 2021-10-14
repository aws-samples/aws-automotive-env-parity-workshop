This project is designed to be used with the AWS-ARM workshop on envionmental parity for automotive utilizing AWS Graviton2 instances.

All the labs use AWS CDK for initial deployment and utilize dedicated VPC.

Currently covered scenarios include :

* CI pipeline for ARM docker container images using CodePipeline, CodeBuild, CodeCommit, and ECR (with docker manifests)
* CI pipeline for running container on Graviton 2 EC2 instance
* EC2 instance with sample container running on Graviton2 instance type

Future work being planned but not yet implemented:

* EKS cluster with arm64 nodegroups
