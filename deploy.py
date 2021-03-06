#!/usr/bin/env python

from __future__ import print_function
import os
import sys
from time import sleep
import boto3
import commands
from botocore.exceptions import ClientError

APP_NAME = os.getenv('BITBUCKET_REPO_SLUG')
COMMIT_HASH = os.getenv('BITBUCKET_COMMIT')
TAG = commands.getoutput("git symbolic-ref HEAD | cut -d/ -f3- | sed -e 's/release\-//'")
COMMIT_DESCRIPTION = commands.getoutput("git log --oneline -n1")
BUILD_NAME = APP_NAME + "-" + TAG + "-" + COMMIT_HASH + ".zip"
BUILD_FILE_LOCATION = "/tmp/" + BUILD_NAME
BUCKET_KEY = os.getenv('EB_APPLICATION_NAME') + '/' + BUILD_NAME

def create_build(version):
    global BUILD_FILE_LOCATION
    print("Creating the build file...")
    build = commands.getoutput('git archive --format=zip HEAD > ' + BUILD_FILE_LOCATION)
    return True

def upload_to_s3(artifact):
    global BUCKET_KEY
    global BUILD_NAME

    print("Uploading the build file to s3 bucket...")

    try:
        client = boto3.client('s3')
    except ClientError as err:
        print("Failed to create boto3 client.\n" + str(err))
        return False

    try:
        client.put_object(
            Body=open(artifact, 'rb'),
            Bucket=os.getenv('EB_BUCKET_S3'),
            Key=BUCKET_KEY
        )
    except ClientError as err:
        print("Failed to upload build file to S3.\n" + str(err))
        return False
    except IOError as err:
        print("Failed to access " + BUILD_NAME + " in directory.\n" + str(err))
        return False

    return True

def create_new_version():
    global BUCKET_KEY
    global BUILD_NAME
    global COMMIT_DESCRIPTION

    print("Creating ElasticBeanstalk Application Version...")

    try:
        client = boto3.client('elasticbeanstalk')
    except ClientError as err:
        print("Failed to create boto3 client.\n" + str(err))
        return False

    try:
        response = client.create_application_version(
            ApplicationName=os.getenv('EB_APPLICATION_NAME'),
            VersionLabel=BUILD_NAME,
            Description=COMMIT_DESCRIPTION,
            SourceBundle={
                'S3Bucket': os.getenv('EB_BUCKET_S3'),
                'S3Key': BUCKET_KEY
            },
            Process=True
        )
    except ClientError as err:
        print("Version already exists.\n")
        return True

    try:
        if response['ResponseMetadata']['HTTPStatusCode'] is 200:
            return True
        else:
            print(response)
            return False
    except (KeyError, TypeError) as err:
        print(str(err))
        return False

def deploy_new_version():
    global BUILD_NAME

    print("Deploying the new version...")

    try:
        client = boto3.client('elasticbeanstalk')
    except ClientError as err:
        print("Failed to create boto3 client.\n" + str(err))
        return False

    try:
        response = client.update_environment(
            ApplicationName=os.getenv('EB_APPLICATION_NAME'),
            EnvironmentName=os.getenv('EB_APPLICATION_ENVIRONMENT'),
            VersionLabel=BUILD_NAME,
        )
    except ClientError as err:
        print("Failed to update environment.\n" + str(err))
        return False

    return True

def main():
    if not create_build(TAG):
        sys.exit(1)
    else:
        print("Build file "+ BUILD_FILE_LOCATION + " created successfully.\n")

    if not upload_to_s3(BUILD_FILE_LOCATION):
        sys.exit(1)
    else:
        print("Build file "+ BUILD_NAME + " upload successfully to bucket.\n")

    if not create_new_version():
        sys.exit(1)
    else:
        print("ElasticBeanstalk Version was not deployed, already existent version.\n")

    sleep(5)

    if not deploy_new_version():
        sys.exit(1)
    else:
        print("Application Deployed successfully in ElasticBeanstalk.\n")

if __name__ == "__main__":
    main()
