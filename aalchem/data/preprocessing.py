import pandas as pd
from aalchem.data.strings import Text
from aalchem.data.datasets import get_product_smiles_from_reaction, get_reactant_smiles_from_reaction


def pandas_to_gemini_training_data(
        df: pd.DataFrame,
        text_input_column: str,
        output_column: str,
        preprompt: str = '') -> list[dict]:
    """
    Convert a pandas dataframe to a format suitable for Gemini fine-tuning.

    Args:
        df (pd.DataFrame): The input dataset.
        text_input_column (str): The column name for the input text.
        output_column (str): The column name for the output text.
        preprompt (str, optional): A string to prepend to each input. Defaults to ''.

    Returns:
        List of dictionaries with text_input and output keys (as required by the Gemini API)
    """
    return [{"text_input": preprompt + row[text_input_column], "output": row[output_column]} for _, row in df.iterrows()]


def dataset_to_gemini(
        df: pd.DataFrame,
        reaction_name_column: str = None,
        reaction_class_column: str = None,
        preprompt: str = '') -> list[dict]:
    """
    Convert a pandas dataframe to a format suitable for Gemini fine-tuning.

    Args:
        dataset (pd.DataFrame): The input dataset.
        text_input_column (str): The column name for the input text.
        output_column (str): The column name for the output text.
        preprompt (str, optional): A string to prepend to each input. Defaults to ''.

    Returns:
        list[dict]: A list of dictionaries with 'text_input' and 'output' keys.
    """
    list_of_dicts = []
    
    for _, row in df.iterrows():
        
        llm_input = preprompt.format(
            product=row['products'], 
            reaction_class=row[reaction_class_column], 
            reaction_name=row[reaction_name_column]
        )
        
        target_output = row['reactants']

        list_of_dicts.append({"text_input": llm_input, "output": target_output})
    return list_of_dicts
