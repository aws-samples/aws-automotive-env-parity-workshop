# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

#!/usr/bin/env python3

from aws_cdk import core

from cdk.vpc_base.vpc import CdkVpcStack
from cdk.pipeline.pipeline import CdkPipelineStack
from cdk.batch_pipeline.batch import CdkBatchStack


class AwsEnvParity(core.App):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            self.stack_name = "yolo-application"
            self.base_module = CdkVpcStack(self, self.stack_name + "-base")
            self.pipeline_module = CdkPipelineStack(self, self.stack_name + "-pipeline", self.base_module.vpc)
            self.batch_module = CdkBatchStack(self, self.stack_name + "-batch-pipeline", self.base_module.vpc)

if __name__ == '__main__':
    app = AwsEnvParity()
    app.synth()
