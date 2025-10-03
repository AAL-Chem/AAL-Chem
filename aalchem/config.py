import os
import datetime
import yaml
from dataclasses import dataclass, field
from dotenv import load_dotenv
from aalchem.utils.base_conf import BaseConfig
from collections import OrderedDict
from typing import Any
from pathlib import Path
import aalchem.data.prompts as prompts


@dataclass
class paths:
    ##  Root directory
    ## Directories
    ROOT_STR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ROOT: Path = Path(ROOT_STR)

    RESULTS: Path = ROOT / 'results'
    MODELS: Path = ROOT / 'models'
    LOGS: Path = ROOT / 'logs'
    DATA: Path = ROOT / 'data'
    PROMPTS: Path = ROOT / 'prompts'
    PLOTS: Path = ROOT / 'plots'
    DEFAULT_TEST_SET_PATH_TRANSITION: Path = DATA / 'uspto50k_graphretro_canonicalized_TEST_atom_and_bond_changes_final_subsample_5_examples_per_reaction_name.csv'
    DEFAULT_TEST_SET_PATH_POSITION:   Path = DATA / 'uspto50k_graphretro_canonicalized_TEST_atom_and_bond_changes_final_subsample_5_examples_per_reaction_name.csv'

    ## Files
    dotenv_file: Path = ROOT / 'backend.env'

# Load environment variables from .env file
load_dotenv(str(paths.dotenv_file))


@dataclass
class ExperimentConfig(BaseConfig):
    """
    Configuration for an experiment.
    """
    model_name: str = "gpt-5"
    n_samples: int = None # if None, all samples will be used
    thinking: bool = True
    thinking_budget_tokens: int = 20000
    start_index: int = 0
    reasoning: str = "high"  # "low", "medium", "high"
    verbosity: str = "high"  # "low", "medium", "high"
    use_examples: bool = True

    date: str = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    suffix: str = ''
    experiment_name: str = f"{model_name.replace('-', '_').replace('.', '_')}{suffix}"

    ## Paths
    prompt_template_path: Path = paths.PROMPTS / 'transition_model_prompt.md'
    eval_set_filepath: Path = paths.DEFAULT_TEST_SET_PATH_TRANSITION
    train_filepath: Path = paths.DATA / 'uspto50k_graphretro_canonicalized_TRAIN_atom_and_bond_changes_final_subsample_5_examples_per_reaction_name.csv'
    results_path: Path = paths.RESULTS / 'transition_model' / experiment_name
    
    
@dataclass
class PositionExperimentConfig(BaseConfig):
    """
    Configuration for a reaction position prediction experiment.

    """
    model_name: str = "claude-sonnet-4-20250514"
    n_samples: int = None # if None, all samples will be used
    thinking: bool = True
    thinking_budget_tokens: int = 20000
    start_index: int = 390
    reasoning: str = "low"  # "low", "medium", "high"
    verbosity: str = "low"  # "low", "medium", "high"

    date: str = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    suffix: str = ''
    experiment_name: str = f"{model_name.replace('-', '_').replace('.', '_')}{suffix}"
    data_path: Path = paths.DEFAULT_TEST_SET_PATH_POSITION
    prompt_template_path: Path = paths.PROMPTS / 'position_model_uspto50k.md'
    results_path: Path = paths.RESULTS / 'position_model' / experiment_name
    

#######################
### Finetuning configuration
#######################

@dataclass
class ModelConfig(BaseConfig):
    """
    Finetuned model configuration.
    """
    temperature: float = 1
    top_p: float = 0.95
    top_k: int = 64
    system_prompt: str = ''
    project: str = 'kablelis-ai-463115'
    location: str = 'europe-west4'
    checkpoint: int = None
    endpoint: str = None
    inference: bool = False
    max_output_tokens: int = 32000
    use_prompt: bool = False


### Main configuration class
@dataclass
class TrainingConfig(BaseConfig):
    """
    Configuration for training a model.
    """
    ## Run configuration
    name: str = f"retrollm-{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    checkpoint_interval: int = 1
    source_model: str = "models/gemini-2.0-flash-001-tuning"
    epoch_count: int = 1
    batch_size: int = 64  # 4-64 range
    temperature: float = 0.5

    ## Dataset configuration
    dataset_name: str = "processed/uspto_50k_train_sample_processed"
    system_prompt: str = prompts.FT_PROMPT

    ## Wandb configuration
    wandb: bool = False
    wandb_project: str = "retrollm-v0.1-data-augmentation"
    wandb_entity: str = "retrollm"

    ## Configuration classes
    model: ModelConfig = field(default_factory=ModelConfig)
    dataset: Any = None
    builder: Any = None
