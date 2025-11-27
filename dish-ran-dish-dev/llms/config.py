from utils import constants as CONST

# Base configuration for all models
BASE_MODEL_CONFIG = {
    "project_id": CONST.WATSONX_PROJECT_ID,
    "url": CONST.WATSONX_URL,
    "apikey": CONST.WATSONX_API_KEY,
}

# Model-specific configurations
MODEL_CONFIGS = {
    "chat": {
        "model_id": CONST.WATSONX_MODEL_ID_MISTRAL_SMALL,
        "params": {
            "decoding_method": "greedy",
            "max_new_tokens": 4000,
            "min_new_tokens": 0,
            "temperature": 0,
        }
    },
    "supervisor": {
        "model_id": CONST.WATSONX_MODEL_ID_MISTRAL_MEDIUM,
        "params": {
            "decoding_method": "greedy",
            "max_new_tokens": 10000,
            "min_new_tokens": 0,
            "temperature": 0,
            "repetition_penalty": 1.1,
            "stop_sequences": []
        }
    },
    "ran_device": {
        "model_id": CONST.WATSONX_MODEL_ID_MISTRAL_SMALL,
        "params": {
            "decoding_method": "greedy",
            "max_new_tokens": 40000,
            "min_new_tokens": 0,
            "max_tokens": 100000,
            "temperature": 0.1,
            "repetition_penalty": 1.2,
            "stop_sequences": []
        }
    },
    "ran_qa": {
        "model_id": CONST.WATSONX_MODEL_ID_MISTRAL_SMALL,
        "params": {
            "decoding_method": "greedy",
            "max_new_tokens": 4000,
            "min_new_tokens": 0,
            "max_tokens": 50000,            
            "temperature": 0.1,
            "repetition_penalty": 1.2,
            "stop_sequences": []
        }
    },    
    "ran_pm": {
        "model_id": CONST.WATSONX_MODEL_ID_MISTRAL_SMALL,
        "params": {
            "decoding_method": "greedy",
            "max_new_tokens": 4000,
            "min_new_tokens": 0,
            "max_tokens": 50000,              
            "temperature": 0.1,
            "repetition_penalty": 1.2,
            "stop_sequences": []
        }
    },    
    "summarize": {
        "model_id": CONST.WATSONX_MODEL_ID_MISTRAL_MEDIUM,
        "params": {
            "decoding_method": "greedy",
            "max_new_tokens": 500,
            "min_new_tokens": 0,
            "temperature": 0,
            "repetition_penalty": 1.2,
            "stop_sequences": []
        }
    },    
    "ran_qa_relevance": {
        "model_id": CONST.WATSONX_MODEL_ID_LLAMA,
        "params": {
            "decoding_method": "greedy",
            "max_new_tokens": 8000,
            "min_new_tokens": 0,
            "temperature": 0.2,
            "repetition_penalty": 1.2,
            "stop_sequences": []
        }
    },    
    "extract": {
        "model_id": CONST.WATSONX_MODEL_ID_MISTRAL_MEDIUM,
        "params": {
            "decoding_method": "greedy",
            "max_new_tokens": 10000,
            "max_tokens": 50000,   
            "min_new_tokens": 0,
            "temperature": 0,
            "stop_sequences": []
        }
    },
    "ran_automation": {
        "model_id": CONST.WATSONX_MODEL_ID_MISTRAL_SMALL,
        "params": {
            "decoding_method": "greedy",
            "max_new_tokens": 10000,
            "max_tokens": 4000,
            "min_new_tokens": 0,
            "temperature": 0,
            "top_k": 25,
            "stop_sequences": []
        }
    },
    "ran_config_qa": {
        "model_id": CONST.WATSONX_MODEL_ID_MISTRAL_SMALL,
        "params": {
            "decoding_method": "greedy",
            "repetition_penalty": 1.1,
            "max_new_tokens": 4000,
            "min_new_tokens": 0,
            "temperature": 0,
            "stop_sequences": []
        }
    },    
    # "kpi_readout": {
    #     "model_id": CONST.WATSONX_MODEL_ID_MISTRAL_MEDIUM,
    #     "params": {
    #         "decoding_method": "greedy",
    #         "max_new_tokens": 20000,
    #         "max_tokens": 20000,   
    #         "min_new_tokens": 0,
    #         "temperature": 0,
    #         "stop_sequences": [],
    #         "repetition_penalty": 1.1,
    #     }
    # }
    "kpi_readout": {
        "model_id": CONST.WATSONX_MODEL_ID_GPT_120B,
        "params": {
            'decoding_method': 'greedy',
            'max_new_tokens': 20000,
            'min_new_tokens': 0,
            'max_tokens': 20000,
            'temperature': 0,
            'stop_sequences': [],
            'repetition_penalty': 1.1,
        }
    }
} 