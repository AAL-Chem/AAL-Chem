from typing import List, Dict, Any, Union
import logging
from dataclasses import dataclass
from abc import ABC, abstractmethod

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("template_populator")

@dataclass
class BasePopulatedTemplate(ABC):
    """Base class for populated templates with common validation."""
    id: str
    prompt: str
    
    def __post_init__(self):
        """Validate that all required fields are populated."""
        required_fields = self.get_required_fields()
        for field_name in required_fields:
            field_value = getattr(self, field_name, None)
            
            # Check if field is None (missing/not set)
            if field_value is None:
                raise ValueError(f"Required field '{field_name}' is missing")
            
            # For strings, check if empty or whitespace-only
            if isinstance(field_value, str) and not field_value.strip():
                raise ValueError(f"Required field '{field_name}' is empty")
            
            # For other types (like lists), None check above is sufficient
            # Empty lists [] are valid values
    
    @abstractmethod
    def get_required_fields(self) -> List[str]:
        """Return list of required field names for this template type."""
        pass


class TaskSpecificTemplatePopulator(ABC):
    """Abstract base class for task-specific template populators."""
    
    def __init__(self, template_path: str):
        self.template_path = template_path
        self.template = self._load_template()
    
    def _load_template(self) -> str:
        """Load the template from the specified path."""
        try:
            with open(self.template_path, 'r') as f:
                template = f.read()
            
            logger.info(f"Loaded template from {self.template_path}")
            return template
            
        except Exception as e:
            logger.error(f"Error loading template: {e}")
            raise
    
    @abstractmethod
    def populate_templates(self, data_points: List[Dict[str, Any]]) -> List[BasePopulatedTemplate]:
        """Populate templates with data points for specific task type."""
        pass

