import json
import pandas as pd
from typing import Dict, List, Tuple

class RetrosynthesisEvaluator:
    """
    A class to match JSON results with initial dataframe and create comparison dataframes.
    """
    
    def __init__(self, initial_df: pd.DataFrame, results_data: List[Dict]):
        """
        Initialize the evaluator with initial dataframe and results data.
        
        Args:
            initial_df: DataFrame containing ground truth data with 'id' column
            results_data: List of dictionaries containing result data
        """
        self.initial_df = initial_df.copy()
        self.results_data = results_data
        self.matched_pairs = []

    def _validate_canonicalized_match(self, df_row: pd.Series, json_result: Dict) -> bool:
        """
        Validate that canonicalized products match between dataframe and JSON.
        
        Args:
            df_row: Row from the initial dataframe
            json_result: JSON result entry
            
        Returns:
            True if products match, False otherwise
        """
        # Get canonicalized products from both sources
        df_product = df_row.get('canonicalized_product', None)
        
        # Try to get canonicalized product from template_data
        json_product = None
        if 'template_data' in json_result:
            json_product = json_result['template_data'].get('canonicalized_product', None)
        
        # Both must exist for comparison
        if df_product is None or json_product is None:
            return False

        # Compare canonicalized products (normalize whitespace)
        return df_product == json_product

    def add_results_to_dataframe(self) -> pd.DataFrame:
        """
        Add result columns to the original dataframe.
        
        Returns:
            Original DataFrame with added template_data and parsed_response columns
        """
        # Create a lookup dictionary from the results data for faster access
        results_lookup = {str(result.get('id')): result for result in self.results_data}
        
        # Initialize the new columns
        template_data_col = []
        response_content_col = []  # Initialize the newly added column
        parsed_response_col = []
        failed_json_parsing_col = []  # Initialize the newly added column
        reasoning_trace_col = []  # Initialize the newly added column
        usage_stats_col = []  # Initialize the newly added column
        
        # Process each row in the initial dataframe
        for row_number, df_row in self.initial_df.iterrows():
            # Check if this row has a match in JSON results using the row number as ID
            row_id = str(row_number)
            if row_id in results_lookup and self._validate_canonicalized_match(df_row, results_lookup[row_id]):
                json_result = results_lookup[row_id]

                # Add template_data from JSON
                template_data = json_result.get('template_data')
                template_data_col.append(json.dumps(template_data) if template_data else '')

                # Add response_content from JSON
                response_content = json_result.get('response_content')
                response_content_col.append(json.dumps(response_content) if response_content else '')

                # Add parsed_response from JSON
                parsed_response = json_result.get('parsed_response')
                parsed_response_col.append(json.dumps(parsed_response) if parsed_response else '')

                # Add failed_json_parsing from JSON
                failed_json_parsing = json_result.get('failed_json_parsing')
                failed_json_parsing_col.append(failed_json_parsing)

                # Add reasoning_trace
                reasoning_trace = json_result.get('reasoning_trace')
                reasoning_trace_col.append(json.dumps(reasoning_trace) if reasoning_trace else '')

                # Add usage_stats
                usage_stats = json_result.get('usage_stats')
                usage_stats_col.append(json.dumps(usage_stats) if usage_stats else '')

            else:
                # No match found - add empty JSON fields
                template_data_col.append('')
                response_content_col.append('')  # Add empty string for new column
                parsed_response_col.append('')
                failed_json_parsing_col.append(json.dumps(True))  # Add true as string for new column
                reasoning_trace_col.append('')  # Add empty string for new column
                usage_stats_col.append(json.dumps({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}))  # Add empty string for new column

        # Add the new columns to the dataframe
        self.initial_df['template_data'] = template_data_col
        self.initial_df['response_content'] = response_content_col  # Add the new column to DataFrame
        self.initial_df['parsed_response'] = parsed_response_col
        self.initial_df['failed_json_parsing'] = failed_json_parsing_col  # Add the new column to DataFrame
        self.initial_df['reasoning_trace'] = reasoning_trace_col  # Add the new column to DataFrame
        self.initial_df['usage_stats'] = usage_stats_col  # Add the new column to DataFrame
        
        return self.initial_df

class RetrosynthesisAnalysis:
    def __init__(self, initial_df: pd.DataFrame, results_data: List[Dict]):
        self.evaluator = RetrosynthesisEvaluator(initial_df, results_data)

    def get_matched_dataframe(self) -> pd.DataFrame:
        """
        Returns the original dataframe with added result columns.
        """
        return self.evaluator.add_results_to_dataframe()

def main(csv: str, json: str, export: str)  -> pd.DataFrame:
    """
    python retrollm/vllm/position_model/evaluation/result_extractor.py \
  --csv data/evaluation/uspto50_atom_bond_changes_splitted_product_reagents_reactants/uspto50k_test_atom_and_bond_changes_final.csv \
  --json run/extracted_results.json \
  --export run/temp_results/uspto50k_test_atom_and_bond_changes_final_results.csv
    """

    initial_df = pd.read_csv(csv)
    with open(json, "r") as f:
        results_data = json.load(f)


    analysis = RetrosynthesisAnalysis(initial_df, results_data)
    matched_df = analysis.get_matched_dataframe()

    # print summary statistics of how many matches were found and how many were not
    total_rows = len(initial_df)
    matched_rows = matched_df[matched_df['template_data'] != ''].shape[0]
    unmatched_rows = total_rows - matched_rows
    print(f"Total rows: {total_rows}, Matched rows: {matched_rows}, Unmatched rows: {unmatched_rows}")

    if export:
        matched_df.to_csv(export, index=False)
        print(f"Exported comparison to {export}")
    return matched_df


if __name__ == "__main__":
    import pandas as pd
    import json
    from typing import Dict, List

    import argparse

    parser = argparse.ArgumentParser(description="Retrosynthesis Evaluation")
    parser.add_argument("--csv", required=True, help="Path to ground truth CSV file")
    parser.add_argument("--json", required=True, help="Path to results JSON file")
    parser.add_argument("--export", required=False, help="Path to export comparison CSV")
    args = parser.parse_args()
    main(args.csv, args.json, args.export)