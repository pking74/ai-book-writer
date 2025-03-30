"""Configuration for the book generation system"""
import os
from typing import Dict, List

def get_config(local_url: str = "https://openrouter.ai/api/v1") -> Dict:
    """Get the configuration for the agents"""
    
    # Basic config for local LLM
    config_list = [{
        'model': 'google/gemma-3-27b-it',
        'base_url': local_url,
        'api_key': "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"
    }]

    # Common configuration for all agents
    agent_config = {
        "seed": 42,
        "temperature": 0.7,
        "config_list": config_list,
        "timeout": 600,
        "cache_seed": None
    }
    
    return agent_config
