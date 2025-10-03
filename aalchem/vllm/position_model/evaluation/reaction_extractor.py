import json
import pandas as pd
from typing import Dict, List, Union
from dataclasses import dataclass, asdict

@dataclass
class ReactionData:
    """Data class to store reaction information with prefixed fields."""
    
    # Template fields
    template_id: str
    # template_prompt: str # we could extract the prompt but thats just too much.
    template_canonicalized_product: str
    template_rxn_insight_name: str
    template_rxn_insight_class: str
    template_rxn_insight_class_retro: str
    template_changed_atom_sites: str
    template_changed_atom_and_bond_sites: str
    
    # Predicted fields
    predicted_disconnection: str
    predicted_forwardReaction: str
    predicted_isInOntology: bool
    predicted_forwardReactionClass: str
    predicted_retrosynthesis_importance: int
    predicted_priority: int
    predicted_rationale: str
    
    # General fields
    general_failed_json_parsing: bool
    general_reasoning_trace: str
    general_prompt_tokens: int
    general_total_tokens: int
    general_completion_tokens: int
    
    def __post_init__(self):
        """Validate that all fields are present and properly populated."""
        # Check string fields are not empty (excluding changed_atom_sites and rationale which can be missing)
        string_fields = [
            'template_id', # 'template_prompt', 
            'template_canonicalized_product',
            'template_rxn_insight_name', 'template_rxn_insight_class', 
            'template_rxn_insight_class_retro', 'template_changed_atom_and_bond_sites',
            'predicted_disconnection', 'predicted_forwardReaction', 'predicted_forwardReactionClass'
        ]
        
        for field_name in string_fields:
            value = getattr(self, field_name)
            value = str(value)
            
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Field '{field_name}' must be a non-empty string, got: {repr(value)}")
        
        # Special validation for rationale - can be missing but warn if so
        if self.predicted_rationale is None or (isinstance(self.predicted_rationale, str) and not self.predicted_rationale.strip()):
            print(f"Warning: Missing rationale for reaction '{self.predicted_forwardReaction}' in template '{self.template_id}'")
            # Set default value for missing rationale
            object.__setattr__(self, 'predicted_rationale', "No rationale provided")
        
        # Special validation for changed atom sites - at least one must be present
        atom_sites = self.template_changed_atom_sites
        atom_and_bond_sites = self.template_changed_atom_and_bond_sites
        
        # template_changed_atom_sites can be NaN/None, but template_changed_atom_and_bond_sites must always be present
        if not isinstance(atom_and_bond_sites, str) or not atom_and_bond_sites.strip():
            raise ValueError("Field 'template_changed_atom_and_bond_sites' must be a non-empty string")
        
        # If atom_sites is provided, it must be a valid string
        if atom_sites is not None and not pd.isna(atom_sites):
            if not isinstance(atom_sites, str) or not atom_sites.strip():
                raise ValueError("Field 'template_changed_atom_sites' when provided must be a non-empty string")
        
        # Check boolean fields
        if not isinstance(self.predicted_isInOntology, bool):
            raise ValueError(f"Field 'predicted_isInOntology' must be boolean, got: {type(self.predicted_isInOntology)}")
        
        if not isinstance(self.general_failed_json_parsing, bool):
            raise ValueError(f"Field 'general_failed_json_parsing' must be boolean, got: {type(self.general_failed_json_parsing)}")
        
        # Check integer fields are non-negative
        int_fields = [
            'predicted_retrosynthesis_importance', 'predicted_priority',
            'general_prompt_tokens', 'general_total_tokens', 'general_completion_tokens'
        ]
        
        for field_name in int_fields:
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"Field '{field_name}' must be a non-negative integer, got: {repr(value)}")

class DataTransformer:
    """Simple transformation class for processing dataframes."""
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform dataframe by processing template data, failed json, and usage stats.
        
        Args:
            df: Input dataframe
            
        Returns:
            Transformed dataframe with expanded rows
        """
        reaction_objects = []
        ground_truth_data = []
        expected_reaction_count = 0
        
        # Define columns to exclude from ground truth data
        excluded_columns = {'template_data', 'parsed_response', 'failed_json_parsing', 'reasoning_trace', 'usage_stats'}
        
        # Debug: Print available columns and what will be kept for ground truth
        available_columns = set(df.columns)
        gt_columns = available_columns - excluded_columns
        print(f"Debug: Total columns in input: {len(available_columns)}")
        print(f"Debug: Excluded columns: {excluded_columns}")
        print(f"Debug: Ground truth columns ({len(gt_columns)}): {sorted(gt_columns)}")
        
        for idx, row in df.iterrows():
            try:
                # Parse JSON strings from the DataFrame
                template_data = json.loads(row["template_data"])
                parsed_response = json.loads(row['parsed_response'])
                failed_json_parsing = row["failed_json_parsing"]
                if failed_json_parsing:
                    reasoning_trace = "No reasoning trace extracted because of failed JSON parsing"
                else:
                    reasoning_trace = row["reasoning_trace"]
                usage_stats = json.loads(row["usage_stats"])
                
                # Create ground truth row by excluding processed columns
                ground_truth_row = {col: row[col] for col in df.columns if col not in excluded_columns}
                
                # Debug: Validate ground truth row has expected columns
                if idx == 0:  # Only print for first row to avoid spam
                    print(f"Debug: Ground truth row has {len(ground_truth_row)} fields: {sorted(ground_truth_row.keys())}")

                # Extract template data - handle NaN values for changed_atom_sites
                template_info = {
                    'template_id': template_data['id'],
                    # 'template_prompt': template_data['prompt'],
                    'template_canonicalized_product': template_data['canonicalized_product'],
                    'template_rxn_insight_name': template_data['rxn_insight_name'],
                    'template_rxn_insight_class': template_data['rxn_insight_class'],
                    'template_rxn_insight_class_retro': template_data['rxn_insight_class_retro'],
                    'template_changed_atom_sites': template_data['changed_atom_sites'],  # Can be None/NaN
                    'template_changed_atom_and_bond_sites': template_data['changed_atom_and_bond_sites']  # Must be present
                }
                
                # Extract general data - all fields must be present
                general_info = {
                    'general_failed_json_parsing': failed_json_parsing,
                    'general_reasoning_trace': reasoning_trace,
                    'general_prompt_tokens': usage_stats.get('prompt_tokens', 0),
                    'general_total_tokens': usage_stats.get('total_tokens', 0),
                    'general_completion_tokens': usage_stats.get('completion_tokens', 0),
                }
                # Only process if JSON parsing was successful
                if failed_json_parsing:
                    reaction_data = ReactionData(
                        **template_info,
                        predicted_disconnection="JSON parsing failed",
                        predicted_forwardReaction="JSON parsing failed",
                        predicted_isInOntology=False,  # Use boolean default
                        predicted_forwardReactionClass="JSON parsing failed",
                        predicted_retrosynthesis_importance=0,  # Use integer default
                        predicted_priority=0,  # Use integer default
                        predicted_rationale="JSON parsing failed - unable to extract rationale",
                        **general_info,
                    )

                    reaction_objects.append(reaction_data)
                    ground_truth_data.append(ground_truth_row.copy())
                    expected_reaction_count += 1
                    continue  # Skip to next row, don't process parsed_response

                # Process disconnections from parsed_response (only if JSON parsing succeeded)
                disconnection_sides = parsed_response.get('disconnections', [])
                for disconnection in disconnection_sides:
                    if isinstance(disconnection, dict) and 'disconnection' in disconnection:
                        disconnection_str = disconnection['disconnection']
                        reactions = disconnection.get('reactions', [])
                        
                        # Count expected reactions
                        expected_reaction_count += len(reactions)

                        # For each reaction in the nested structure, create a ReactionData object
                        for reaction in reactions:
                            # Create ReactionData object for validation
                            reaction_data = ReactionData(
                                **template_info,
                                predicted_disconnection=disconnection_str,
                                predicted_forwardReaction=reaction["forwardReaction"],
                                predicted_isInOntology=reaction["isInOntology"],
                                predicted_forwardReactionClass=reaction["forwardReactionClass"],
                                predicted_retrosynthesis_importance=reaction["Retrosynthesis Importance"],
                                # set the priority to 100 if the model fails to predict any.
                                predicted_priority=reaction.get("Priority", 100),
                                predicted_rationale=reaction.get("rationale", None),
                                **general_info,
                            )
                            
                            reaction_objects.append(reaction_data)
                            
                            # Add corresponding ground truth data for this reaction (filtered)
                            ground_truth_data.append(ground_truth_row.copy())

            except Exception as e:
                print(f"Error processing row {idx}: {e}")
        
        # Convert ReactionData objects to DataFrame
        df_data = [asdict(reaction) for reaction in reaction_objects]
        result_df = pd.DataFrame(df_data)
        
        # Create ground truth DataFrame
        ground_truth_df = pd.DataFrame(ground_truth_data)
        
        # Debug: Print DataFrame shapes and column info
        print(f"Debug: Reaction data shape: {result_df.shape}")
        print(f"Debug: Ground truth data shape: {ground_truth_df.shape}")
        print(f"Debug: Ground truth columns: {list(ground_truth_df.columns)}")
        
        # Assertion to verify ground truth data length matches extracted data
        assert len(ground_truth_df) == len(result_df), (
            f"Ground truth data length ({len(ground_truth_df)}) does not match extracted data length "
            f"({len(result_df)}). Data alignment error."
        )
        
        # Check for column name conflicts before merging
        reaction_cols = set(result_df.columns)
        gt_cols = set(ground_truth_df.columns)
        overlapping_cols = reaction_cols & gt_cols
        if overlapping_cols:
            print(f"Warning: Column name conflicts detected: {overlapping_cols}")
        
        # Always prefix ground truth columns with 'gt_'
        print("Adding 'gt_' prefix to all ground truth columns")
        ground_truth_df = ground_truth_df.add_prefix('gt_')
        
        # Merge the two DataFrames horizontally with ground_truth_df first
        result_df = pd.concat([ground_truth_df, result_df], axis=1)
        
        # Assertion to verify all reactions were extracted correctly
        assert len(result_df) == expected_reaction_count, (
            f"Extracted dataframe length ({len(result_df)}) does not match expected reaction count "
            f"({expected_reaction_count}). Some reactions may have been lost during processing."
        )
        
        print(f"Validation passed: Extracted {len(result_df)} reactions matching expected count of {expected_reaction_count}")
        print(f"Ground truth data validation passed: {len(ground_truth_df)} GT rows match {len(result_df)} extracted rows")
        
        return result_df


def extract_reactions(input_file: str, output_file: str, json_column: str = 'parsed_response'):
    """
    Main function to load, transform, and save dataframe with all ReactionData fields.
    
    Args:
        input_file: Path to input CSV file
        output_file: Path to output CSV file with populated ReactionData fields
        json_column: Column containing JSON data to parse
    """
    # Load dataframe
    print(f"Loading dataframe from {input_file}")
    df = pd.read_csv(input_file)
    print(f"Loaded {len(df)} rows")
    
    # Transform data using the extractor
    print("Transforming data using ReactionData extractor...")
    transformer = DataTransformer()
    populated_df = transformer.transform(df)
    print(f"Created {len(populated_df)} reaction entries")
    
    # Display summary of extracted data
    if len(populated_df) > 0:
        print(f"Extracted fields: {list(populated_df.columns)}")
        print(f"Sample disconnections: {populated_df['predicted_disconnection'].unique()[:5].tolist()}")
        print(f"Sample reactions: {populated_df['predicted_forwardReaction'].unique()[:5].tolist()}")
    
    # Save the fully populated dataframe
    print(f"Saving populated dataframe to {output_file}")
    populated_df.to_csv(output_file, index=False)
    print(f"Successfully saved {len(populated_df)} reaction entries with all ReactionData fields!")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python reaction_extractor.py <input_file> <output_file> [json_column]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    json_column = sys.argv[3] if len(sys.argv) > 3 else 'parsed_response'
    
    extract_reactions(input_file, output_file, json_column)