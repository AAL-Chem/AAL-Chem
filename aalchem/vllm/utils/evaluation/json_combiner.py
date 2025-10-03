import json
import os
import re
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from abc import ABC, abstractmethod
#import json_repair

class ResponseParser(ABC):
    """Abstract base class for parsing model responses."""
    
    @abstractmethod
    def parse(self, content: str, example_id: Optional[str] = None) -> Tuple[Optional[str], Optional[Dict[str, Any]], bool]:
        """Parse response content into reasoning trace and JSON output.
        
        Args:
            content: Raw response content from the model
            example_id: Optional ID of the example for error reporting
            
        Returns:
            Tuple of (reasoning_trace, parsed_json, failed_parsing)
        """
        pass

class JsonParser(ResponseParser):
    """Parser for model outputs with reasoning content and JSON."""
    
    def parse(self, content: str, example_id: Optional[str] = None) -> Tuple[Optional[str], Optional[Dict[str, Any]], bool]:
        """Parse response content.
        
        Expected format:
        - Reasoning content before </think>
        - JSON content after </think>
        """
        reasoning_trace = None
        parsed_json = None
        failed_parsing = False
        
        # Split at </think>
        if '</think>' in content:
            parts = content.split('</think>', 1)
            reasoning_trace = parts[0].strip()
            json_content = parts[1].strip()
        else:
            # No </think> found, treat entire content as JSON
            json_content = content.strip()
        
        # Parse JSON content
        if json_content:
            print(f"Parsing Json Content {example_id}")

            # Extract content between ```json and ``` markers - get the LAST occurrence
            if '```json' in json_content and '```' in json_content:
                # Find the last occurrence of ```json
                start_marker = '```json'
                start_pos = json_content.rfind(start_marker)
                if start_pos != -1:
                    # Look for the closing ``` after the last opening marker
                    content_start = start_pos + len(start_marker)
                    end_pos = json_content.find('```', content_start)
                    if end_pos != -1:
                        json_content = json_content[content_start:end_pos].strip()

            try:
                parsed_json = json.loads(json_content)
                #parsed_json = json_repair.loads(json_content)
            except Exception as e:
                error_msg = f"JSON decode error for example {example_id}: {e}" if example_id else f"JSON decode error: {e}"
                print(error_msg)
                failed_parsing = True
                parsed_json = json_content

            # the fields in the parsed response must be either "disconnections" (position_prompt) or "reaction_analysis" (transition) to make sure its a real json
            if parsed_json:
                if not any(field in parsed_json for field in ["disconnections", "reaction_analysis"]):
                    error_msg = f"Invalid JSON structure for example {example_id}: {parsed_json}" if example_id else f"Invalid JSON structure: {parsed_json}"
                    print(error_msg)
                    failed_parsing = True
        
        return reasoning_trace, parsed_json, failed_parsing

class JsonCombiner:
    """Class for extracting response data from JSON files."""
    
    def __init__(self, responses_folder: str, parser: Optional[ResponseParser] = None):
        """Initialize the ResultExtractor.
        
        Args:
            responses_folder: Folder containing response JSON files
            parser: Parser instance for extracting reasoning and JSON from responses
        """
        self.responses_folder = responses_folder
        self.response_files = []
        self.parser = parser or JsonParser()
    
    def find_response_files(self) -> List[str]:
        """Find all response_n.json files in folder and sort by n."""
        folder = Path(self.responses_folder)
        response_files = []
        
        for file_path in folder.glob("response_*.json"):
            match = re.match(r'response_(\d+)\.json', file_path.name)
            if match:
                response_files.append((int(match.group(1)), str(file_path)))
        
        # Sort by response number
        response_files.sort(key=lambda x: x[0])
        self.response_files = [path for _, path in response_files]
        print(f"Found {len(self.response_files)} response files")
        return self.response_files

    def extract_response_data(self, response_file: str) -> Dict[str, Any]:
        """Extract response data from JSON file."""
        try: 
            with open(response_file, 'r') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error loading JSON file {response_file}: {e}")
            return {
                'id': {},
                'template_data': {},
                'response_content': "",
                'usage': {}
            }
        
        return {
            'id': data.get('template_data', {}).get('id'),
            'template_data': data.get('template_data', {}),
            'response_content': data.get('response', {}).get('choices', [{}])[0].get('message', {}).get('content', ''),
            'usage': data.get('response', {}).get('usage', {})
        }

    def extract_all_results(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Extract data from all response files.
        
        Returns:
            A tuple containing two lists:
            - extracted_results: A list of successfully parsed results.
            - failed_jsons: A list of responses where JSON parsing failed.
        """
        if not self.response_files:
            self.find_response_files()
        
        extracted_results = []
        failed_jsons = []
        
        for response_file in self.response_files:
            # Extract response data from the raw JSON file
            response_data = self.extract_response_data(response_file)
            
            # Parse the model's response content to separate reasoning and JSON
            reasoning_trace, parsed_json, failed_parsing = self.parser.parse(response_data['response_content'], response_data['id'])

            # If JSON parsing fails, add it to the failed list
            if failed_parsing:
                print(f"Warning: Could not parse JSON response for file {response_file}, example ID: {response_data['id']}")
                failed_jsons.append({
                    'file_path': response_file,
                    'id': response_data['id'],
                    'response_content': response_data['response_content']
                })
            
            # Combine all extracted data into a single result dictionary
            result = {
                'file_path': response_file,
                'id': response_data['id'],
                'template_data': response_data['template_data'],
                'response_content': response_data['response_content'],
                'parsed_response': parsed_json,
                'failed_json_parsing': failed_parsing,
                'reasoning_trace': reasoning_trace,
                'usage_stats': response_data['usage']
            }
            
            extracted_results.append(result)
        
        return extracted_results, failed_jsons
    
    def save_extracted_data(self, output_path: str, data: List[Dict[str, Any]]) -> None:
        """Save extracted data as JSON."""
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Saved {len(data)} extracted entries to {output_path}")
    
    def save_failed_jsons(self, output_path: str, failed_data: List[Dict[str, Any]]) -> None:
        """Save failed JSONs to a file."""
        if not failed_data:
            print(f"No failed JSON entries to save.")
            return
        
        output_dir = Path(output_path).parent
        failed_output_path = output_dir / "failed_jsons.json"
        
        with open(failed_output_path, 'w') as f:
            json.dump(failed_data, f, indent=2)
            
        print(f"Saved {len(failed_data)} failed JSON entries to {failed_output_path}")

    def run(self, output_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Run the extraction pipeline and optionally save results."""
        # Get both successful results and failed JSONs
        results, failed_jsons = self.extract_all_results()
        
        if output_path:
            # Save the successfully parsed results
            self.save_extracted_data(output_path, results)
            # Save the responses that failed to parse
            self.save_failed_jsons(output_path, failed_jsons)
        
        # Return only the successful results
        return results

def parse_jsons(folder: str, output: str) -> List[Dict[str, Any]]:
    """
    Parse all JSON files in the given folder and combine them into a single list of results.
    """
    response_parser = JsonParser()
    extractor = JsonCombiner(folder, response_parser)
    results = extractor.run(output)
    print(f"Extracted {len(results)} results")
    if output:
        print(f"Results saved to {output}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract and combine JSON response data from multiple files")
    parser.add_argument("--folder", help="Folder containing response JSON files")
    parser.add_argument("-o", "--output", help="Output JSON file path (optional)")
    parser.add_argument("--parser", choices=["json"], default="json", help="Parser type to use (default: json)")
    
    args = parser.parse_args()
    
    results = parse_jsons(args.folder, args.output)
    
