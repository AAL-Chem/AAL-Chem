from google.cloud import storage
from google.cloud.storage import Bucket 
from pprint import pprint
from aalchem.config import paths
from aalchem.data.strings import Text
import json
import os
from pathlib import Path


class CloudDataset:
    def __init__(self, project: str, location='europe-west4'):
        self.project_name = project
        self.location = location
        self.storage_client = storage.Client(project=project)
        
    def list_buckets(self, verbose=True) -> list[str]:
        """
        Returns a list of current buckets
        """
        buckets = [bucket for bucket in self.storage_client.list_buckets()]
        if verbose:
            pprint([f'{i}: {bucket}' for i, bucket in enumerate(buckets)])
        return buckets                  

    def list_blobs(self, bucket_name: str=None, bucket_id: int=None) -> list[str]:
        """
        Lists all the blobs in a bucket
        """
        assert(bucket_name is not None or bucket_id is not None, 'Either bucket name or index should be provided')
        bucket_name = self.list_buckets()[bucket_id] if bucket_id is not None else bucket_name
        return [blob.name for blob in self.storage_client.list_blobs(bucket_name)]

    def create_new_bucket(self, bucket_name: str) -> Bucket:
        """
        Creates a new bucket
        """
        bucket = self.storage_client.bucket(bucket_name=bucket_name, user_project=self.project_name)
        bucket.storage_class = 'COLDLINE'
        new_bucket = self.storage_client.create_bucket(bucket, location=self.location, project=self.project_name)
        print(f'Created bucket {bucket_name} in {new_bucket.location}...')
        return new_bucket

    def delete_bucket(self, bucket_name: str=None, bucket_id: int=None) -> None:
        """
        Deletes a bucket
        """
        if bucket_name is None and bucket_id is not None:
            bucket = self.list_buckets()[bucket_id]
        else:
            bucket = self.storage_client.bucket(bucket_name=bucket_name)
        print(f'Deleting bucket {bucket.name}...')
        bucket.delete(force=True)

    def upload_blob(self, bucket_name, source_file_path, destination_blob_name) -> None:
        """
        Uploads a file to the bucket
        """
        bucket = self.storage_client.bucket(bucket_name=bucket_name)
        blob = bucket.blob(destination_blob_name)

        blob.upload_from_filename(source_file_path, if_generation_match=0)
        print(f'File {source_file_path} uploaded to {destination_blob_name}...')

    def upload_dataset(
            self, 
            dataset,
            system_prompt: str, 
            bucket_name: str, 
            blob_name: str
        ) -> str:
        """
        Pass
        """
        if bucket_name not in [bucket.name for bucket in self.list_buckets()]:
            print(f'Creating a new bucket at {self.project_name}/{self.location}: {bucket_name}')
            bucket = self.create_new_bucket(bucket_name)
        else:
            bucket = self.storage_client.bucket(bucket_name=bucket_name)

        dataset_path = paths.DATA / 'jsonl' / dataset.name+'.jsonl'
        dataset_to_jsonl(
            dataset=dataset,
            system_prompt=system_prompt,
            output_path=dataset_path
        )
        
        uri = f'gs://{bucket_name}/{blob_name}.jsonl'
        print(f'Creating a new blob {blob_name} in {bucket_name} using {dataset.name} dataset... \n URI: {uri}')
        self.upload_blob(
            bucket_name=bucket_name,
            source_file_path=dataset_path,
            destination_blob_name=f'{blob_name}.jsonl'
        )
        return uri
    

def dataset_to_jsonl(
        dataset, 
        system_prompt: str, 
        output_path: str | Path, 
        start: int = 0, 
        end: int = -1
    ) -> str:
    """
    Pass
    """
    df = dataset.df[start:end]
    json_list = []
    print(df.columns)

    for index, row in df.iterrows():
        json_prompt = jsonize_request(
            system_prompt=system_prompt,
            user_input=Text.from_json(row['output']).text, # Corrupted samples
            model_output=Text.from_json(row['input']).text # Original samples
        )
        json_list.append(json_prompt)
    pprint(json_list[0])

    with open(output_path, 'w') as f:
        for json_request in json_list:
            f.write(json.dumps(json_request) + '\n')
    print(f'Created new dataset at {output_path} ')

    return output_path


def jsonize_request(
        system_prompt: str, 
        user_input: str, 
        model_output: str = None
    ):
    """
    Pass
    """

    model_output = "" if model_output is None else model_output
    
    json = {
        'systemInstruction': {
            'role': 'system',
            'parts': [{'text': system_prompt}]
        },
        'contents': [
            {
                'role': 'user',
                'parts': [{'text': user_input}]
            },
            {
                'role': 'model',
                'parts': [{'text': model_output}]
            }
        ]
    }
    return json
