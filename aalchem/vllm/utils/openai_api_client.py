import asyncio
import httpx
import os
import json
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from template_populator import BasePopulatedTemplate


class OpenAICompatibleClient:
    """
    A client for managing queued requests to OpenAI-compatible APIs with controlled concurrency.
    """
    
    def __init__(
        self,
        model_name,
        output_dir,
        server_url,
        max_concurrent_requests=5,
        timeout=300  # 5 minutes in seconds
    ):
        """
        Initialize the PrototypingClient with configurable settings.
        
        Args:
            model_name (str): The model to use (must be downloaded in Ollama)
            output_dir (str): Directory to save output JSON files
            server_url (str): Ollama server URL
            max_concurrent_requests (int): Maximum number of concurrent requests
            timeout (int): Request timeout in seconds
        """
        self.model_name = model_name
        self.output_dir = output_dir
        self.server_url = server_url
        self.timeout = timeout
        self.max_concurrent_requests = max_concurrent_requests
        
        # Internal request queue and tracking
        self.request_queue = asyncio.Queue()
        self.active_requests = 0
        self.request_counter = 0
        self.session: Optional[httpx.AsyncClient] = None
        self.workers_started = False
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def __aenter__(self):
        """Enter the async context manager, starting the client."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager, stopping the client."""
        await self.stop()

    async def start(self):
        """Start the client and its worker tasks."""
        if self.session is None:
            self.session = httpx.AsyncClient()
        
        if not self.workers_started:
            # Start worker tasks
            self.worker_tasks = [
                asyncio.create_task(self._worker()) 
                for _ in range(self.max_concurrent_requests)
            ]
            self.workers_started = True
            print(f"Started {self.max_concurrent_requests} worker tasks")
    
    async def stop(self):
        """Stop the client and clean up resources."""
        if self.workers_started:
            # Signal workers to stop by putting None in the queue
            for _ in range(self.max_concurrent_requests):
                await self.request_queue.put(None)
            
            # Wait for all workers to finish
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
            self.workers_started = False
        
        if self.session:
            await self.session.aclose()
            self.session = None
        
        print("Client stopped and resources cleaned up.")
    
    async def submit_request(self, populated_template: 'BasePopulatedTemplate') -> str:
        """
        Submit a request to the queue.
        
        Args:
            populated_template (BasePopulatedTemplate): The populated template containing prompt and metadata
            
        Returns:
            str: The request ID for tracking
        """
        if not self.workers_started:
            raise RuntimeError("Client not started. Please use 'async with' or call start() first.")
        
        await self.request_queue.put(populated_template)
        
        print(f"Submitted request: {populated_template.id}")
        return populated_template.id
    
    async def _worker(self):
        """Worker task that processes requests from the queue."""
        while True:
            # Get next request from queue
            populated_template = await self.request_queue.get()
            
            # None is the signal to stop
            if populated_template is None:
                break
            
            try:
                await self._process_request(populated_template)
            except Exception as e:
                print(f"Error in worker processing request {populated_template.id if populated_template else 'unknown'}: {e}")
            finally:
                self.request_queue.task_done()
    
    async def _process_request(self, populated_template: 'BasePopulatedTemplate'):
        """Process a single request using BasePopulatedTemplate data."""
        self.active_requests += 1
        print(f"Processing request: {populated_template.id} (Active: {self.active_requests})")
        
        try:
            json_data = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": populated_template.prompt}]
            }
            
            response = await self.session.post(
                self.server_url, 
                json=json_data, 
                timeout=self.timeout
            )
            response.raise_for_status()
            response_json = response.json()
            
            # Dynamically extract all fields from the template dataclass
            template_data = {}
            for field_name in populated_template.__dataclass_fields__:
                template_data[field_name] = getattr(populated_template, field_name)
            
            # Combine template data with response
            output_data = {
                "template_data": template_data,
                "response": response_json
            }
            
            # Save the combined JSON response
            save_path = os.path.join(self.output_dir, f"response_{populated_template.id}.json")
            with open(save_path, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            print(f"Successfully processed and saved response_{populated_template.id}.json")

        except httpx.HTTPStatusError as e:
            print(f"HTTP error for request {populated_template.id}: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"Error processing request {populated_template.id}: {e}")
        
        finally:
            self.active_requests -= 1
    
    async def wait_for_completion(self):
        """Wait for all queued requests to complete."""
        await self.request_queue.join()
        print("All requests completed")
    
    def get_queue_size(self) -> int:
        """Get the current size of the request queue."""
        return self.request_queue.qsize()
    
    def get_active_requests(self) -> int:
        """Get the number of currently active requests."""
        return self.active_requests