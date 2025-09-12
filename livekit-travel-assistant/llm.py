import os
from langchain_community.llms import LlamaCpp
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import BaseMessage
from langchain_core.prompts import PromptTemplate
import logging
from config import MODEL_1B_PATH, MODEL_3B_PATH
from typing import List, Optional, Dict, Any, Iterator, AsyncIterator
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class DynamicLlamaCpp(BaseLanguageModel):
    llm_1b: Optional[LlamaCpp] = None
    llm_3b: Optional[LlamaCpp] = None

    def __init__(self):
        super().__init__()
        if not os.path.exists(MODEL_1B_PATH) or not os.path.exists(MODEL_3B_PATH):
            raise FileNotFoundError(f"Model files not found: {MODEL_1B_PATH}, {MODEL_3B_PATH}")
        
        try:
            self.llm_1b = LlamaCpp(
                model_path=MODEL_1B_PATH,
                n_ctx=1024,
                n_gpu_layers=50,
                temperature=0.1,
                max_tokens=1000,
                verbose=True,
                stop=["\n", "Please", "<|eot_id|>", "Result:", "Note:", "This is", ";"]
            )
            self.llm_3b = LlamaCpp(
                model_path=MODEL_3B_PATH,
                n_ctx=1024,
                n_gpu_layers=50,
                temperature=0.1,
                max_tokens=1000,
                verbose=True,
                stop=["\n", "Please", "<|eot_id|>", "Result:", "Note:", "This is", ";"]
            )
        except Exception as e:
            logger.error(f"Error loading Llama models: {e}")
            raise

    def _select_llm(self, input_text: str):
        input_tokens = len(self.llm_1b.client.tokenize(input_text.encode('utf-8')))
        selected_llm = self.llm_1b if input_tokens < 100 else self.llm_3b
        logger.info(f"Selected model: {'1B' if input_tokens < 100 else '3B'} for {input_tokens} tokens")
        logger.debug(f"Input prompt: {input_text}")
        return selected_llm

    def invoke(self, input: Any, config: Optional[Dict] = None, **kwargs) -> Any:
        if isinstance(input, list):
            prompt_text = "\n".join([msg.content if hasattr(msg, 'content') else str(msg) for msg in input])
        else:
            prompt_text = str(input)
        selected_llm = self._select_llm(prompt_text)
        return selected_llm.invoke(prompt_text, config=config, **kwargs)

    def bind(self, **kwargs):
        # Use LangChain's built-in bind to wrap the LLM with additional kwargs
        return super().bind(**kwargs)

    def generate(self, prompts: List[str], **kwargs) -> List[str]:
        selected_llm = self._select_llm(prompts[0] if prompts else "")
        return selected_llm.generate(prompts, **kwargs)

    async def agenerate(self, prompts: List[str], **kwargs) -> List[str]:
        selected_llm = self._select_llm(prompts[0] if prompts else "")
        return await selected_llm.agenerate(prompts, **kwargs)

    def predict(self, text: str, **kwargs) -> str:
        selected_llm = self._select_llm(text)
        return selected_llm.predict(text, **kwargs)

    async def apredict(self, text: str, **kwargs) -> str:
        selected_llm = self._select_llm(text)
        return await selected_llm.apredict(text, **kwargs)

    def predict_messages(self, messages: List[BaseMessage], **kwargs) -> BaseMessage:
        selected_llm = self._select_llm(messages[0].content if messages else "")
        return selected_llm.predict_messages(messages, **kwargs)

    async def apredict_messages(self, messages: List[BaseMessage], **kwargs) -> BaseMessage:
        selected_llm = self._select_llm(messages[0].content if messages else "")
        return await selected_llm.apredict_messages(messages, **kwargs)

    def stream(self, input: str, **kwargs) -> Iterator[str]:
        selected_llm = self._select_llm(input)
        return selected_llm.stream(input, **kwargs)

    async def astream(self, input: str, **kwargs) -> AsyncIterator[str]:
        selected_llm = self._select_llm(input)
        return await selected_llm.astream(input, **kwargs)

    def generate_prompt(self, prompts: List[PromptTemplate], stop: Optional[List[str]] = None, **kwargs) -> Any:
        selected_llm = self._select_llm(prompts[0].template if prompts else "")
        return selected_llm.generate([prompt.template for prompt in prompts], stop=stop, **kwargs)

    async def agenerate_prompt(self, prompts: List[PromptTemplate], stop: Optional[List[str]] = None, **kwargs) -> Any:
        selected_llm = self._select_llm(prompts[0].template if prompts else "")
        return await selected_llm.agenerate([prompt.template for prompt in prompts], stop=stop, **kwargs)

    async def astream_events(self, input: Any, config: Optional[Dict] = None, **kwargs) -> AsyncIterator[Dict]:
        raise NotImplementedError("astream_events not implemented")

    @property
    def _llm_type(self) -> str:
        return "dynamic_llama_cpp"

    def __call__(self, *args, **kwargs):
        return self.invoke(*args, **kwargs)