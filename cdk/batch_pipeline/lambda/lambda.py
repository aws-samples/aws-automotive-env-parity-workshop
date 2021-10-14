import json
import os
import boto3
import subprocess
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)
pipeline = boto3.client('codepipeline')

def lambda_handler(event, context):
    logger.info(dict(**os.environ))
    logger.info(event)
    logger.info(context)

    s3 = boto3.client('s3')
    batch = boto3.client('batch')

    batchProcessingJobName =  os.environ.get("BATCH_JOB_NAME")
    batchProcessingJobQueue =  os.environ.get("BATCH_JOB_QUEUE")
    batchJobDefinition =  os.environ.get("BATCH_JOB_DEFINITION")
    region = os.environ.get('AWS_REGION')
    bucket = os.environ.get('S3_BUCKET')
    
    batchResponse = batch.submit_job(jobName=batchProcessingJobName, 
                                     jobQueue=batchProcessingJobQueue, 
                                     jobDefinition=batchJobDefinition,
                                     containerOverrides={
                                         "environment": [
                                             {"name": "HELLO", "value": "WORLD"},
                                             {"name": "S3_BUCKET", "value": bucket},
                                         ],
                                         "memory": 512
                                     })
    
    logger.info('##BATCH SUBMIT JOB RESPONSE\r' + str(batchResponse))
    
    job_id = event['CodePipeline.job']['id']
    batch_submit_job_repsonse = batchResponse['ResponseMetadata']['HTTPStatusCode']
    
    if batch_submit_job_repsonse == 200:
        # Tell codepipeline that the Lambda funtions invokation of AWS Batch was successfull
        response = pipeline.put_job_success_result(
            jobId=job_id
        )
    else:
        # Otherwise, the pipeline stage fails
        response = pipeline.put_job_failure_result(
            jobId=job_id,
            failureDetails={'type': 'JobFailed', 'message': batchResponse}
        )
    return response
    