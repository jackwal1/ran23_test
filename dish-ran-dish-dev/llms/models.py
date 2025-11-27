import time
from rich.console import Console
from langchain_ibm import ChatWatsonx, WatsonxLLM
from .config import BASE_MODEL_CONFIG, MODEL_CONFIGS

console = Console()

def create_chat_model(model_type: str, verbose: bool = True) -> ChatWatsonx:
    """Create a chat model with the specified configuration."""
    config = MODEL_CONFIGS[model_type]
    return ChatWatsonx(
        model_id=config["model_id"],
        project_id=BASE_MODEL_CONFIG["project_id"],
        url=BASE_MODEL_CONFIG["url"],
        apikey=BASE_MODEL_CONFIG["apikey"],
        params=config["params"],
        verbose=verbose
    )

def create_llm_model(model_type: str, verbose: bool = True) -> WatsonxLLM:
    """Create an LLM model with the specified configuration."""
    config = MODEL_CONFIGS[model_type]
    return WatsonxLLM(
        model_id=config["model_id"],
        project_id=BASE_MODEL_CONFIG["project_id"],
        url=BASE_MODEL_CONFIG["url"],
        apikey=BASE_MODEL_CONFIG["apikey"],
        params=config["params"],
        verbose=verbose
    )

# Initialize all models
start_time = time.perf_counter()

# Chat models
ran_device_chatmodel = create_chat_model("ran_device")
ran_pm_chatmodel = create_chat_model("ran_pm")
ran_qa_chatmodel = create_chat_model("ran_qa")
chatmodel = create_chat_model("chat")
supervisor_model = create_chat_model("supervisor")
extraction_model = create_chat_model("extract")
ran_automation_model = create_chat_model("ran_automation")
ran_config_qa_model = create_chat_model("ran_config_qa")
ran_kpi_readout_model = create_chat_model("kpi_readout")

# # LLM models
summary_model = create_llm_model("summarize")
ran_qa_relevance_model = create_llm_model("ran_qa_relevance")



end_time = time.perf_counter()
elapsed_time = (end_time - start_time) * 1000
console.print(f"[bold green]Model initialization time: {elapsed_time:.2f} ms[/]") 