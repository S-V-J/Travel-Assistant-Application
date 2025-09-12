from llama_cpp import Llama
import os

model_path = os.path.expanduser("~/.llama/checkpoints/Llama3.2-1B-Instruct.gguf")
prompt = """<|start_header_id|>system<|end_header_id>
You are a helpful assistant. For simple greetings like 'Hello, world!', respond with a concise, direct acknowledgment such as 'Hello!' or 'Hi there!'. If no specific response is generated, default to 'Hello!'. For other inputs, respond directly and relevantly. Always ensure a response is provided.
<|eot_id|><|start_header_id|>user<|end_header_id>
Hello, world!
<|eot_id|><|start_header_id|>assistant<|end_header_id>"""

try:
    llm = Llama(
        model_path=model_path,
        n_ctx=2048,
        n_gpu_layers=-1,  # Full GPU offload
        verbose=True
    )
    response = llm(prompt, max_tokens=50, temperature=0.3, stop=["<|eot_id|>"])  # Lower temperature, add stop token
    print(f"Response: {response['choices'][0]['text'].strip() or 'Hello!'}")  # Fallback to 'Hello!' if empty
except Exception as e:
    print(f"Error: {e}")