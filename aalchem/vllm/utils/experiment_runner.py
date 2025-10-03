import json
import asyncio
import logging
from typing import List, Dict, Any
from aalchem.vllm.utils.openai_api_client import OpenAICompatibleClient
from aalchem.vllm.utils.template_populator import BasePopulatedTemplate

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
            required_task_fields = ["prompt_template_path", "output_dir"]
            for field in required_task_fields:
                if field not in config["task_config"]:
                    raise ValueError(f"Missing required field '{field}' in task_config")

            # Validate data subfields
            logger.info(f"Note we are not checking if the data fields are present as those are task dependent.")
            
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
