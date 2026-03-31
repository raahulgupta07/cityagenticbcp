"""
Agent configuration.
"""
import os
from config.settings import AGENT_CONFIG

AGENT_ENABLED = AGENT_CONFIG["enabled"]
MAX_TURNS = AGENT_CONFIG["max_turns"]
MAX_TOKENS = AGENT_CONFIG["max_tokens"]
TEMPERATURE = AGENT_CONFIG["temperature"]
