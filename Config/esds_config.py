"""
Sovereign Scaling Configuration - ESDS Config
Model-agnostic configuration using LiteLLM provider strings.
Enables seamless switching between ollama/llama3.2 and esds/deepseek-v4.
"""

import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


class ModelProvider(Enum):
    """Supported model providers."""
    OLLAMA = "ollama"
    ESDS = "esds"           # Sovereign DeepSeek
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    LOCAL = "local"


@dataclass
class ModelConfig:
    """Configuration for a model."""
    provider: ModelProvider
    model_name: str
    litellm_string: str     # LiteLLM provider format
    base_url: Optional[str]
    api_key_env: Optional[str]
    max_tokens: int
    temperature: float
    supports_vision: bool
    supports_streaming: bool
    cost_per_1k_tokens: float  # For budget tracking
    priority: int              # Lower = higher priority
    fallback_to: Optional[str] # Model name to fallback to


class ESDSConfig:
    """
    Enterprise Sovereign DeepSeek Configuration.
    Manages model switching with graceful fallbacks.
    """
    
    # Default model configurations
    MODELS = {
        # Sovereign DeepSeek V4 (Primary for production)
        "deepseek-v4": ModelConfig(
            provider=ModelProvider.ESDS,
            model_name="deepseek-v4",
            litellm_string="esds/deepseek-v4",
            base_url=os.getenv("ESDS_BASE_URL", "https://esds.sovereign.ai/v1"),
            api_key_env="ESDS_API_KEY",
            max_tokens=8000,
            temperature=0.1,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_tokens=0.002,
            priority=1,
            fallback_to="deepseek-v3"
        ),
        
        # DeepSeek V3 (Fallback)
        "deepseek-v3": ModelConfig(
            provider=ModelProvider.ESDS,
            model_name="deepseek-v3",
            litellm_string="esds/deepseek-v3",
            base_url=os.getenv("ESDS_BASE_URL", "https://esds.sovereign.ai/v1"),
            api_key_env="ESDS_API_KEY",
            max_tokens=4096,
            temperature=0.1,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_tokens=0.001,
            priority=2,
            fallback_to="llama3.2"
        ),
        
        # Ollama Llama 3.2 (Local development)
        "llama3.2": ModelConfig(
            provider=ModelProvider.OLLAMA,
            model_name="llama3.2",
            litellm_string="ollama/llama3.2",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            api_key_env=None,  # No key needed for local
            max_tokens=4096,
            temperature=0.1,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_tokens=0.0,  # Free local
            priority=3,
            fallback_to="llama3.1"
        ),
        
        # Ollama Llama 3.1 (Local fallback)
        "llama3.1": ModelConfig(
            provider=ModelProvider.OLLAMA,
            model_name="llama3.1",
            litellm_string="ollama/llama3.1",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            api_key_env=None,
            max_tokens=4096,
            temperature=0.1,
            supports_vision=False,
            supports_streaming=True,
            cost_per_1k_tokens=0.0,
            priority=4,
            fallback_to=None
        ),
        
        # OpenAI GPT-4 (Premium fallback)
        "gpt-4o": ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4o",
            litellm_string="openai/gpt-4o",
            base_url=None,
            api_key_env="OPENAI_API_KEY",
            max_tokens=4096,
            temperature=0.1,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_tokens=0.01,
            priority=5,
            fallback_to="gpt-4o-mini"
        ),
        
        # OpenAI GPT-4o Mini (Budget fallback)
        "gpt-4o-mini": ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4o-mini",
            litellm_string="openai/gpt-4o-mini",
            base_url=None,
            api_key_env="OPENAI_API_KEY",
            max_tokens=4096,
            temperature=0.1,
            supports_vision=True,
            supports_streaming=True,
            cost_per_1k_tokens=0.0003,
            priority=6,
            fallback_to=None
        ),
    }
    
    # Environment-based defaults
    ENV_DEFAULTS = {
        "production": "deepseek-v4",
        "staging": "deepseek-v3",
        "development": "llama3.2",
        "test": "llama3.1"
    }
    
    def __init__(self, environment: str = None):
        self.environment = environment or os.getenv("ENV", "development")
        self._current_model: str = self.ENV_DEFAULTS.get(self.environment, "llama3.2")
        self._fallback_chain: List[str] = []
        self._build_fallback_chain()
    
    def _build_fallback_chain(self):
        """Build the fallback chain from current model."""
        self._fallback_chain = [self._current_model]
        
        current = self._current_model
        while current and current in self.MODELS:
            next_model = self.MODELS[current].fallback_to
            if next_model and next_model not in self._fallback_chain:
                self._fallback_chain.append(next_model)
                current = next_model
            else:
                break
    
    def get_model(self, model_name: str = None) -> ModelConfig:
        """Get model configuration."""
        name = model_name or self._current_model
        return self.MODELS.get(name)
    
    def get_litellm_string(self, model_name: str = None) -> str:
        """Get LiteLLM provider string for the model."""
        config = self.get_model(model_name)
        return config.litellm_string if config else "ollama/llama3.2"
    
    def get_api_key(self, model_name: str = None) -> Optional[str]:
        """Get API key for the model."""
        config = self.get_model(model_name)
        if config and config.api_key_env:
            return os.getenv(config.api_key_env)
        return None
    
    def is_model_available(self, model_name: str) -> bool:
        """Check if a model is available (API key set or local)."""
        config = self.get_model(model_name)
        if not config:
            return False
        
        if config.provider == ModelProvider.OLLAMA:
            # Check if Ollama is running
            try:
                import requests
                resp = requests.get(f"{config.base_url}/api/tags", timeout=2)
                return resp.status_code == 200
            except:
                return False
        
        # Check API key for cloud providers
        if config.api_key_env:
            return os.getenv(config.api_key_env) is not None
        
        return True
    
    def get_available_model(self) -> Optional[ModelConfig]:
        """Get the first available model from the fallback chain."""
        for model_name in self._fallback_chain:
            if self.is_model_available(model_name):
                return self.get_model(model_name)
        return None
    
    def switch_model(self, model_name: str) -> bool:
        """Switch to a different model."""
        if model_name in self.MODELS:
            self._current_model = model_name
            self._build_fallback_chain()
            return True
        return False
    
    def get_completion_kwargs(self, model_name: str = None) -> Dict[str, Any]:
        """Get kwargs for LiteLLM completion call."""
        config = self.get_model(model_name) or self.get_available_model()
        
        if not config:
            raise RuntimeError("No available model found")
        
        kwargs = {
            "model": config.litellm_string,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
        }
        
        if config.base_url:
            kwargs["api_base"] = config.base_url
        
        if config.api_key_env:
            api_key = os.getenv(config.api_key_env)
            if api_key:
                kwargs["api_key"] = api_key
        
        return kwargs
    
    def estimate_cost(self, tokens: int, model_name: str = None) -> float:
        """Estimate cost for a given number of tokens."""
        config = self.get_model(model_name)
        if not config:
            return 0.0
        return (tokens / 1000) * config.cost_per_1k_tokens
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get summary of current configuration."""
        available = self.get_available_model()
        
        return {
            "environment": self.environment,
            "current_model": self._current_model,
            "active_model": available.model_name if available else None,
            "fallback_chain": self._fallback_chain,
            "litellm_string": self.get_litellm_string(),
            "supports_vision": available.supports_vision if available else False,
            "supports_streaming": available.supports_streaming if available else False
        }


# Usage patterns for LiteLLM integration
def create_completion(
    messages: List[Dict[str, str]], 
    config: ESDSConfig = None,
    model_override: str = None
) -> Dict[str, Any]:
    """
    Create a completion using LiteLLM with automatic fallback.
    
    Usage:
        config = ESDSConfig(environment="production")
        response = create_completion([{"role": "user", "content": "Hello"}], config)
    """
    config = config or ESDSConfig()
    
    try:
        import litellm
        
        kwargs = config.get_completion_kwargs(model_override)
        kwargs["messages"] = messages
        
        response = litellm.completion(**kwargs)
        return {
            "success": True,
            "response": response,
            "model_used": kwargs["model"]
        }
        
    except Exception as e:
        # Try fallback
        for model_name in config._fallback_chain[1:]:
            if config.is_model_available(model_name):
                try:
                    kwargs = config.get_completion_kwargs(model_name)
                    kwargs["messages"] = messages
                    response = litellm.completion(**kwargs)
                    return {
                        "success": True,
                        "response": response,
                        "model_used": kwargs["model"],
                        "fallback": True
                    }
                except:
                    continue
        
        return {
            "success": False,
            "error": str(e),
            "model_attempted": config._current_model
        }


# ============== Trusted Execution Environment (TEE) Support ==============

@dataclass
class TEEConfig:
    """Configuration for Trusted Execution Environment."""
    enabled: bool
    enclave_type: str  # "sgx", "sev", "tdx"
    attestation_url: Optional[str]
    encrypted_memory: bool
    max_enclave_size_mb: int
    gramine_manifest: Optional[str]


class ConfidentialComputing:
    """
    Configures Trusted Execution Environments for sensitive diplomatic processing.
    Supports Intel SGX, AMD SEV, and Intel TDX enclaves.
    """
    
    # TEE configurations
    TEE_CONFIGS = {
        "h100_sgx": TEEConfig(
            enabled=True,
            enclave_type="sgx",
            attestation_url=os.getenv("SGX_ATTESTATION_URL", "https://api.trustedservices.intel.com"),
            encrypted_memory=True,
            max_enclave_size_mb=256 * 1024,  # 256GB for H100
            gramine_manifest="vllm-gramine.manifest"
        ),
        "h200_tdx": TEEConfig(
            enabled=True,
            enclave_type="tdx",
            attestation_url=os.getenv("TDX_ATTESTATION_URL"),
            encrypted_memory=True,
            max_enclave_size_mb=512 * 1024,  # 512GB for H200
            gramine_manifest=None
        ),
        "amd_sev": TEEConfig(
            enabled=True,
            enclave_type="sev",
            attestation_url=os.getenv("SEV_ATTESTATION_URL"),
            encrypted_memory=True,
            max_enclave_size_mb=128 * 1024,
            gramine_manifest=None
        ),
        "disabled": TEEConfig(
            enabled=False,
            enclave_type="none",
            attestation_url=None,
            encrypted_memory=False,
            max_enclave_size_mb=0,
            gramine_manifest=None
        )
    }
    
    def __init__(self, tee_profile: str = None):
        self.profile = tee_profile or os.getenv("TEE_PROFILE", "disabled")
        self.config = self.TEE_CONFIGS.get(self.profile, self.TEE_CONFIGS["disabled"])
    
    def get_vllm_tee_args(self) -> Dict[str, Any]:
        """Get vLLM arguments for TEE-enabled inference."""
        if not self.config.enabled:
            return {}
        
        args = {
            "trust_remote_code": False,
            "enforce_eager": True,  # Disable CUDA graphs in enclave
        }
        
        if self.config.enclave_type == "sgx":
            args.update({
                "cpu_offload_gb": 0,  # Keep all in enclave
                "tensor_parallel_size": 1,  # Single GPU in enclave
            })
        
        return args
    
    def get_gramine_manifest(self) -> Optional[str]:
        """Get Gramine manifest content for SGX enclaves."""
        if not self.config.gramine_manifest:
            return None
        
        # Gramine manifest template for vLLM
        manifest = f'''
# Gramine Manifest for vLLM in SGX Enclave
loader.entrypoint = "file:{{{{ gramine.libos }}}}"
loader.log_level = "error"

# Python vLLM entrypoint
libos.entrypoint = "/usr/bin/python3"

loader.env.LD_LIBRARY_PATH = "/lib:/lib/x86_64-linux-gnu:/usr/lib:/usr/lib/x86_64-linux-gnu"
loader.env.HOME = "/root"
loader.env.CUDA_VISIBLE_DEVICES = "0"

loader.argv = ["python3", "-m", "vllm.entrypoints.openai.api_server",
               "--model", "/models/deepseek-v4",
               "--trust-remote-code", "false",
               "--enforce-eager"]

fs.mounts = [
  {{ path = "/lib", uri = "file:{{{{ gramine.runtimedir() }}}}" }},
  {{ path = "/models", uri = "file:/mnt/models", type = "encrypted" }},
  {{ path = "/tmp", uri = "file:/tmp", type = "tmpfs" }},
]

sgx.enclave_size = "{self.config.max_enclave_size_mb}M"
sgx.thread_num = 64
sgx.remote_attestation = "dcap"

sgx.allowed_files = [
  "file:/dev/nvidia0",
  "file:/dev/nvidiactl",
]

sgx.trusted_files = [
  "file:/usr/bin/python3",
  "file:/models/deepseek-v4/",
]
'''
        return manifest
    
    def encrypt_context(self, context: str) -> bytes:
        """Encrypt diplomatic context for enclave processing."""
        if not self.config.encrypted_memory:
            return context.encode()
        
        # In production, use hardware-backed encryption
        # This is a placeholder for the encryption flow
        import hashlib
        key = hashlib.sha256(os.getenv("ENCLAVE_KEY", "dev").encode()).digest()
        
        # XOR encryption placeholder (use AES-GCM in production)
        encrypted = bytes([b ^ key[i % len(key)] for i, b in enumerate(context.encode())])
        return encrypted
    
    def is_tee_available(self) -> bool:
        """Check if TEE is available on the system."""
        if not self.config.enabled:
            return False
        
        if self.config.enclave_type == "sgx":
            # Check for SGX device
            return os.path.exists("/dev/sgx_enclave") or os.path.exists("/dev/isgx")
        elif self.config.enclave_type == "sev":
            # Check for SEV
            return os.path.exists("/dev/sev")
        elif self.config.enclave_type == "tdx":
            # Check for TDX
            return os.path.exists("/dev/tdx-guest")
        
        return False
    
    def get_attestation_report(self) -> Optional[Dict]:
        """Get remote attestation report for verification."""
        if not self.is_tee_available():
            return None
        
        return {
            "enclave_type": self.config.enclave_type,
            "attestation_url": self.config.attestation_url,
            "status": "ready",
            "encrypted_memory": self.config.encrypted_memory
        }


# Confidential computing singleton
confidential_computing = ConfidentialComputing()

# Default singleton
esds_config = ESDSConfig()
