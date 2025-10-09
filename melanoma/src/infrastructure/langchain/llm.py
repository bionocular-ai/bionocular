"""LangChain-based LLM service for clinical text generation.

This module provides a sophisticated LLM service that leverages LangChain's
LLM integrations while adding model management, prompt templating, and
performance optimizations for clinical text generation.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    from langchain_community.chat_models import ChatOpenAI
from langchain_core.language_models import BaseLLM
from langchain_core.prompts import PromptTemplate

from ...domain.extraction_interfaces import LLMService

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    This class defines the interface for LLM providers, allowing for
    easy extension to support different LLM services.
    """

    @abstractmethod
    def get_llm(self, model_name: str, **kwargs) -> BaseLLM:
        """Get an LLM instance.

        Args:
            model_name: Name of the model
            **kwargs: Additional model parameters

        Returns:
            LLM instance
        """
        pass

    @abstractmethod
    def get_chat_model(self, model_name: str, **kwargs) -> BaseLLM:
        """Get a chat model instance.

        Args:
            model_name: Name of the model
            **kwargs: Additional model parameters

        Returns:
            Chat model instance
        """
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider implementation.

    This class provides OpenAI-specific LLM implementations with
    proper configuration and error handling.
    """

    def get_llm(self, model_name: str, **kwargs) -> BaseLLM:
        """Get an OpenAI LLM instance.

        Args:
            model_name: Name of the model
            **kwargs: Additional model parameters

        Returns:
            ChatOpenAI LLM instance
        """
        try:
            return ChatOpenAI(model_name=model_name, **kwargs)
        except Exception as e:
            logger.error(f"Failed to create OpenAI LLM: {e}")
            raise RuntimeError(f"OpenAI LLM creation failed: {e}") from e

    def get_chat_model(self, model_name: str, **kwargs) -> BaseLLM:
        """Get an OpenAI chat model instance.

        Args:
            model_name: Name of the model
            **kwargs: Additional model parameters

        Returns:
            OpenAI chat model instance
        """
        try:
            return ChatOpenAI(model_name=model_name, **kwargs)
        except Exception as e:
            logger.error(f"Failed to create OpenAI chat model: {e}")
            raise RuntimeError(f"OpenAI chat model creation failed: {e}") from e


class PromptManager:
    """Manages prompt templates for clinical text generation.

    This class encapsulates all prompt management logic including
    template creation, validation, and rendering. It's separated to
    maintain single responsibility and make the prompt management
    logic testable.
    """

    # Default prompt templates
    DEFAULT_PROMPTS = {
        "clinical_qa": """
You are a medical research assistant specializing in melanoma treatments.
Use the following context to answer the user's question about clinical trials, treatments, and research.

Context:
{context}

Question: {question}

Instructions:
1. Provide accurate, evidence-based answers based on the context
2. Include specific details like NCT numbers, trial names, and results when available
3. If the context doesn't contain enough information, say so clearly
4. Focus on clinical trial data, efficacy, safety, and treatment outcomes
5. Use medical terminology appropriately

Answer:
""",
        "clinical_extraction": """
Extract the following clinical information from the provided text:

Text: {text}

Extract:
- Clinical Trial ID (NCT number)
- Treatment Arms
- Primary Endpoints
- Secondary Endpoints
- Efficacy Results
- Safety Results
- Patient Population
- Study Design

Format the response as structured JSON.
""",
        "clinical_summary": """
Summarize the following clinical trial information:

Trial Information: {trial_info}

Provide a concise summary focusing on:
1. Study objective
2. Key findings
3. Clinical significance
4. Safety profile

Summary:
""",
    }

    def __init__(self):
        """Initialize the prompt manager."""
        self._templates: dict[str, PromptTemplate] = {}
        self._load_default_templates()

    def _load_default_templates(self) -> None:
        """Load default prompt templates."""
        for name, template in self.DEFAULT_PROMPTS.items():
            self._templates[name] = PromptTemplate(
                template=template,
                input_variables=self._extract_input_variables(template),
            )

    def _extract_input_variables(self, template: str) -> list[str]:
        """Extract input variables from template string.

        Args:
            template: Template string

        Returns:
            List of input variable names
        """
        import re

        variables = re.findall(r"\{(\w+)\}", template)
        return list(set(variables))

    def get_template(self, name: str) -> PromptTemplate:
        """Get a prompt template by name.

        Args:
            name: Name of the template

        Returns:
            Prompt template

        Raises:
            ValueError: If template not found
        """
        if name not in self._templates:
            raise ValueError(f"Template '{name}' not found")
        return self._templates[name]

    def add_template(
        self, name: str, template: str, input_variables: list[str]
    ) -> None:
        """Add a new prompt template.

        Args:
            name: Name of the template
            template: Template string
            input_variables: List of input variable names
        """
        self._templates[name] = PromptTemplate(
            template=template, input_variables=input_variables
        )
        logger.info(f"Added prompt template: {name}")

    def list_templates(self) -> list[str]:
        """List available prompt templates.

        Returns:
            List of template names
        """
        return list(self._templates.keys())

    def render_template(self, name: str, **kwargs) -> str:
        """Render a prompt template with variables.

        Args:
            name: Name of the template
            **kwargs: Template variables

        Returns:
            Rendered template string
        """
        template = self.get_template(name)
        return template.format(**kwargs)


class LangChainLLMService(LLMService):
    """LangChain-based LLM service for clinical text generation.

    This service provides sophisticated LLM capabilities using LangChain's
    LLM integrations while adding model management, prompt templating, and
    performance optimizations specifically designed for clinical text generation.
    """

    # Supported LLM providers
    PROVIDERS = {
        "openai": OpenAIProvider,
    }

    def __init__(self, provider: str = "openai"):
        """Initialize the LangChain LLM service.

        Args:
            provider: LLM provider to use
        """
        if provider not in self.PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider}")

        self.provider = provider
        self.provider_instance = self.PROVIDERS[provider]()
        self.prompt_manager = PromptManager()

        logger.info(f"LangChain LLM service initialized with provider: {provider}")

    def get_llm(
        self,
        model_name: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> BaseLLM:
        """Get an LLM instance.

        Args:
            model_name: Name of the model
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model parameters

        Returns:
            LLM instance
        """
        try:
            llm_kwargs = {"temperature": temperature, **kwargs}

            if max_tokens:
                llm_kwargs["max_tokens"] = max_tokens

            return self.provider_instance.get_llm(model_name, **llm_kwargs)

        except Exception as e:
            logger.error(f"Failed to get LLM {model_name}: {e}")
            raise RuntimeError(f"LLM creation failed: {e}") from e

    def get_chat_model(
        self,
        model_name: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> BaseLLM:
        """Get a chat model instance.

        Args:
            model_name: Name of the model
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model parameters

        Returns:
            Chat model instance
        """
        try:
            llm_kwargs = {"temperature": temperature, **kwargs}

            if max_tokens:
                llm_kwargs["max_tokens"] = max_tokens

            return self.provider_instance.get_chat_model(model_name, **llm_kwargs)

        except Exception as e:
            logger.error(f"Failed to get chat model {model_name}: {e}")
            raise RuntimeError(f"Chat model creation failed: {e}") from e

    async def generate_response(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 1000,
        model_name: str = "gpt-4o-mini",
    ) -> str:
        """Generate response using the LLM service.

        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            model_name: Model name to use

        Returns:
            Generated response text
        """
        llm = self.get_llm(model_name, temperature=temperature, max_tokens=max_tokens)
        return self.generate_text(llm, prompt)

    def generate_text(self, llm: BaseLLM, prompt: str, **kwargs) -> str:
        """Generate text using an LLM.

        Args:
            llm: LLM instance
            prompt: Prompt text
            **kwargs: Additional generation parameters

        Returns:
            Generated text
        """
        try:
            result = llm.invoke(prompt, **kwargs)
            # LangChain chat models often return AIMessage; extract .content
            try:
                from langchain_core.messages import AIMessage

                if isinstance(result, AIMessage):
                    return result.content or ""
            except Exception:
                pass
            # Fallbacks
            if hasattr(result, "content"):
                return result.content or ""
            return str(result)
        except Exception as e:
            logger.error(f"Text generation failed: {e}")
            raise RuntimeError(f"Text generation failed: {e}") from e

    def generate_with_template(
        self, llm: BaseLLM, template_name: str, **template_vars
    ) -> str:
        """Generate text using a prompt template.

        Args:
            llm: LLM instance
            template_name: Name of the template
            **template_vars: Template variables

        Returns:
            Generated text
        """
        try:
            template = self.prompt_manager.get_template(template_name)
            prompt = template.format(**template_vars)
            return self.generate_text(llm, prompt)
        except Exception as e:
            logger.error(f"Template-based generation failed: {e}")
            raise RuntimeError(f"Template-based generation failed: {e}") from e

    def add_prompt_template(
        self, name: str, template: str, input_variables: list[str]
    ) -> None:
        """Add a new prompt template.

        Args:
            name: Name of the template
            template: Template string
            input_variables: List of input variable names
        """
        self.prompt_manager.add_template(name, template, input_variables)

    def list_prompt_templates(self) -> list[str]:
        """List available prompt templates.

        Returns:
            List of template names
        """
        return self.prompt_manager.list_templates()

    def get_service_statistics(self) -> dict[str, Any]:
        """Get statistics about the LLM service.

        Returns:
            Dictionary containing service statistics
        """
        return {
            "provider": self.provider,
            "available_templates": self.list_prompt_templates(),
            "total_templates": len(self.list_prompt_templates()),
        }
