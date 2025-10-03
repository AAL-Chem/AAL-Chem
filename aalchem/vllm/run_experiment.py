import json
import asyncio
import os
from pathlib import Path
from typing import List, Dict, Any
import logging
import pandas as pd
from aalchem.vllm.utils.openai_api_client import OpenAICompatibleClient
from aalchem.vllm.utils.template_populator import BasePopulatedTemplate
from aalchem.vllm.position_model.template.reaction_position_template import ReactionPositionPopulator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("experiment_runner")

class ExperimentRunner:
    """Runs experiments using pre-populated prompts and the OpenAI compatible client."""
    
    def __init__(self, config_path: str):
        """
        Initialize the experiment runner with a configuration file path.
        
        Args:
            config_path (str): Path to the JSON configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()
        
        # Initialize the API client with config settings
        self.client_config = {
            "model_name": self.config["vllm_config"]["model_name"],
            "server_url": self.config["vllm_config"]["server_url"],
            "timeout": self.config["client_config"]["request_timeout"],
            "output_dir": self.config["task_config"]["output_dir"],
            "max_concurrent_requests": self.config["client_config"]["max_concurrent_requests"]
        }
        
        # Set retry configuration
        self.max_retries = self.config["client_config"].get("max_retries", 1)
        self.retry_delay = self.config["client_config"].get("retry_delay", 5)  # seconds

    def _load_config(self) -> Dict[str, Any]:
        """Load and validate the configuration file."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Validate required fields
            required_fields = [
                "name", "vllm_config", "task_config", "client_config"
            ]
            for field in required_fields:
                if field not in config:
                    raise ValueError(f"Missing required field '{field}' in config")
            
            # Validate vllm_config subfields
            required_vllm_fields = ["model_name", "server_url"]
            for field in required_vllm_fields:
                if field not in config["vllm_config"]:
                    raise ValueError(f"Missing required field '{field}' in vllm_config")
            
            # Validate client_config subfields
            required_client_fields = ["request_timeout", "max_concurrent_requests"]
            for field in required_client_fields:
                if field not in config["client_config"]:
                    raise ValueError(f"Missing required field '{field}' in client_config")
            
            # Validate task_config subfields
            required_task_fields = ["prompt_template_path", "data_path", "output_dir"]
            for field in required_task_fields:
                if field not in config["task_config"]:
                    raise ValueError(f"Missing required field '{field}' in task_config")
            
            logger.info(f"Loaded configuration: {config['name']}")
            return config
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise
    
    async def run_experiment(self, populated_templates: List[BasePopulatedTemplate]):
        """
        Run the experiment using the provided populated templates with retry logic.
        
        Args:
            populated_templates: List of BasePopulatedTemplate dataclass instances
        """
        logger.info(f"Running experiment with {len(populated_templates)} templates")
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Experiment attempt {attempt + 1}/{self.max_retries + 1}")
                
                # Create client and run all requests in batch
                async with OpenAICompatibleClient(**self.client_config) as client:
                    # Submit all populated templates
                    tasks = [
                        client.submit_request(template) 
                        for template in populated_templates
                    ]
                    
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Wait for all requests to complete
                    await client.wait_for_completion()
                    
                logger.info("Experiment completed successfully")
                return  # Success, exit retry loop
                
            except Exception as e:
                logger.error(f"Experiment attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries:
                    logger.info(f"Retrying experiment in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error(f"Experiment failed after {self.max_retries + 1} attempts")
                    raise


async def run_sample_experiment(config_path: str, populated_templates: List[BasePopulatedTemplate]):
    """
    Run a sample experiment using the provided configuration and populated templates.
    
    Args:
        config_path (str): Path to the configuration JSON file
        populated_templates: List of BasePopulatedTemplate dataclass instances
    """
    runner = ExperimentRunner(config_path)
    await runner.run_experiment(populated_templates)


if __name__ == "__main__":
    import sys
    
    # Require config path as command line argument
    if len(sys.argv) < 2:
        logger.error("Usage: python run_experiment.py <config_path>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    
    # Validate config file exists
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)
    
    # Load configuration to get template path
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Create template populator and populate templates
    populator = ReactionPositionPopulator(config["task_config"]["prompt_template_path"])

    reaction_data = pd.read_csv(config["task_config"]["data_path"])
    
    selected_columns = [
        "id", "canonicalized_product", "rxn_insight_name", "rxn_insight_class", "rxn_insight_class_retro",
        "changed_atom_sites", "changed_atom_and_bond_sites"
    ]
    reaction_data = reaction_data[selected_columns]

    # add the row number to id
    reaction_data['id'] = reaction_data.index.astype(str)
    populated_templates = populator.populate_templates(reaction_data.to_dict(orient='records'))

    # Run the experiment
    asyncio.run(run_sample_experiment(config_path, populated_templates))