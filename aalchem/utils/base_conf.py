import json
import yaml
from dataclasses import dataclass
import copy

@dataclass
class BaseConfig:
    """
    Base configuration class.
    """
    #########################################################
    ## Conversion, serialization, and deserialization methods
    def from_dict(self, config: dict):
        for key, value in config.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def to_dict(self):
        return self.__dict__
    
    def to_json(self, path: str):
        ## Change any variable of type Path to str

        dictionary = copy.deepcopy(self.__dict__)
        for key, value in dictionary.items():
            if 'Path' in str(type(value)):
                dictionary[key] = str(value)
        with open(path, "w") as f:
            json.dump(dictionary, f)

    def to_yaml(self, path: str):
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f)

    @classmethod
    def from_json(cls, path: str):
        with open(path, "r") as f:
            return cls(**json.load(f))
        
    @classmethod
    def from_yaml(cls, path: str):
        with open(path, "r") as f:
            return cls(**yaml.load(f, Loader=yaml.FullLoader))
