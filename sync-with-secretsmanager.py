
import os
import logging
import json,yaml
import argparse
import traceback,sys
from boto3 import Session

def setLogger():
    # Setting logging level
    loglevel = os.getenv("LOGLEVEL","INFO")
    numeric_level = getattr(logging, loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel)
    logging.basicConfig(level=numeric_level)

# Script used for updating AWS secrets entries with the values contained in json config files
def init_aws_session():
    # Create a Secrets Manager client
    session = Session()
    client = session.client(
        service_name='secretsmanager'
    )
    return client


def update_secret(secret_arn, jsonString,DryRun=False):
    client = init_aws_session()
    if DryRun:
        logging.info(f"(dryrun) Updating secret entry: {secret_arn}")
        logging.debug(f"(dryrun) Content file: {jsonString}")
        return 0
    logging.info(f"Updating secret entry: {secret_arn}")
    logging.debug(f"Content file: {jsonString}")
    try:
        client.update_secret(SecretId=secret_arn, SecretString=jsonString)
    
    except Exception as e:
        logging.error(f"{traceback.format_exception(*sys.exc_info())} ")
        return 1
    return 0


def get_secret(secret_name):
    client = init_aws_session()

    # In this sample we only handle the specific exceptions for the 'GetSecretValue' API.
    # See https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
    # We rethrow the exception by default.

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'DecryptionFailureException':
            # Secrets Manager can't decrypt the protected secret text using the provided KMS key.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InternalServiceErrorException':
            # An error occurred on the server side.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            # You provided an invalid value for a parameter.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            # You provided a parameter value that is not valid for the current state of the resource.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'ResourceNotFoundException':
            # We can't find the resource that you asked for.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
    else:
        # Decrypts secret using the associated KMS CMK.
        # Depending on whether the secret is a string or binary, one of these fields will be populated.
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
        else:
            decoded_binary_secret = base64.b64decode(get_secret_value_response['SecretBinary'])

    
    return json.loads(secret)


setLogger()

parser = argparse.ArgumentParser("sync-with-secretsmanager")
parser.add_argument('--secret_arn',required=True, nargs='?', help='AWS secret manager ARN  help')
parser.add_argument('--secret_json_file',required=True, nargs='?', help='secret json file help')
parser.add_argument('--prefix_filter_match', type=str, nargs='?', help='Include only prefix filter for matching sequence')
parser.add_argument('--dryrun', nargs='?', help='Dry run')
args = parser.parse_args()
secretARN=args.secret_arn
secretsJsonFile=args.secret_json_file
filter_match=args.prefix_filter_match
filter_match = [s.strip() for s in filter_match.split(",")]
_dryRun=args.dryrun


# Get the Json content from the file
with open(secretsJsonFile) as f: 
    jsonData = yaml.load(f, yaml.SafeLoader) # Load thourhg YAML for safe loading
    # filter content according to this scripts call
    jsonDataFilter = {}
    for key in jsonData:
        matched = False
        for filterMatch in filter_match:
            if key.startswith(filterMatch):
                matched=True
                jsonDataFilter[key] = jsonData[key]
                break
        
    jsonData = jsonDataFilter
    jsonString = json.dumps(jsonData)



result = update_secret(secret_arn=secretARN,jsonString=jsonString,DryRun=_dryRun)
if result > 0:
    logging.error(f"ERROR. Could not update secret manager entry")
    exit(result)

logging.info(f"AWS Secret Manager entry synced succesfully!")
exit(0)
