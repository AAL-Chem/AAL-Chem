from aalchem.config import paths 
import os
import json
import pandas as pd
from tqdm import tqdm

## Functions for postprocessing transition model output jsons

def postprocess_gpt(data: dict) -> dict:
    data['response']['choices'] = [data['response']['output'][1]]
    data['response']['choices'][0]['content'] = data['response']['choices'][0]['content'][0]['text']
    del data['response']['output']
    
    return data


def postprocess_gpt_old_format(data: dict) -> dict:
    """
    Postprocess the GPT old format.
    Does nothing.
    """
    return data

def postprocess_other(data: dict) -> dict:
    del data['response']['created']
    return data

def postprocess_transition_jsons(
        model_name: str,
        model_type: str = 'transition_model',
        postprocessed_json_dir: str = 'jsons_',
        postprocess_fn: callable = None
    ) -> int:
    """
    For postprocessing the transition jsons.
    """
    base_dir = paths.RESULTS / model_type / model_name
    if not os.path.exists(base_dir):
        raise ValueError(f"Directory {base_dir} does not exist.") 
    json_dir = base_dir / 'jsons'
    postprocessed_json_dir = base_dir / postprocessed_json_dir
    os.makedirs(postprocessed_json_dir, exist_ok=True)

    # For mapping numerical ids to uids
    eval_set = pd.read_csv(paths.DEFAULT_TEST_SET_PATH_TRANSITION)
    id_to_num = dict(zip(eval_set['id'], eval_set.index))

    successful = []
    for file in tqdm(os.listdir(json_dir)):
        if file.endswith('.json'):
            try:
                with open(json_dir / file, 'r') as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON in file: {file}")
                print(repr(e))
                continue
            
            file_id = data['template_data']['id']
            # Check if file ID is numeric 
            if str(file_id).isnumeric():
                numerical_id = int(file_id)
            else:
                numerical_id = id_to_num.get(file_id, None)
                if numerical_id is None:
                    print(f"Warning: Could not find numerical ID for file {file}, skipping.")
                    continue
            try:
                data['template_data']['id'] = int(numerical_id)
                if postprocess_fn is not None:
                    data = postprocess_fn(data)
            except Exception as e:
                print(f"Warning: Could not find template_data['id'] in file {file}, using alternative postprocessing function. {e}")
                data = postprocess_gpt_old_format(data)
            
            successful.append(numerical_id)

            out_file_path = postprocessed_json_dir / f'response_{str(numerical_id)}.json'
            with open(out_file_path, 'w') as f:
                json.dump(data, f, indent=4)
    return len(successful)


def postprocess_and_merge(
    model_name: str,
    sister_run: str,
    model_type: str = 'transition_model'
    ) -> None:
    """
    For postprocessing the transition jsons.
    """
    
    json_dir = paths.RESULTS / model_type/  model_name / 'jsons'
    sister_json_dir = paths.RESULTS / model_type / sister_run / 'jsons'
    postprocessed_json_dir = paths.RESULTS / model_type / model_name / 'jsons_'
    os.makedirs(postprocessed_json_dir, exist_ok=True)

    eval_set = pd.read_csv(paths.DEFAULT_TEST_SET_PATH_TRANSITION)
    print(eval_set.columns)
    print(eval_set.shape)
    ## Create a dict where the index column is matched to id in the eval set
    num_to_id = dict(zip(eval_set.index, eval_set['id']))
    id_to_num = {v: k for k, v in num_to_id.items()}

    for file in os.listdir(json_dir):
        if file.endswith('.json'):
            with open(json_dir / file, 'r') as f:
                data = json.load(f)
            with open(sister_json_dir / file, 'r') as f:
                sister_data = json.load(f)
            sister_content = sister_data['response']
            

            print(data['response'])
            hash_id = data['template_data']['id']
            numerical_id = id_to_num.get(hash_id, None)
            print(numerical_id, hash_id)
            del data['response']['created']
            data['response']['choices'][0]['message']['content'] = sister_content

            data['template_data']['id'] = int(numerical_id)
            out_file_path = postprocessed_json_dir / 'response_' + str(numerical_id) + '.json'
            with open(out_file_path, 'w') as f:
                json.dump(data, f, indent=4)
