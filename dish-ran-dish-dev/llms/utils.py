from .models import summary_model
from langchain.prompts import PromptTemplate


# summarize content shared
async def generate_summary(
        input_text: str,
        old_summary: str,
) -> str:
    """
    Use this tool to generate a summary of the input string.

    Args:
        input_str (str): The text to be summarized
        old_summary (str): The old summary to be included

    Returns:
        str: The summarized text
    """
    
    SUMMARY_PROMPT = """
    This is summary of the conversation to date: {summary}\n\n
    Extend the summary by taking into account the following: {input_text}
    """
    print(input_text)
    print(old_summary)
    prompt_template = PromptTemplate.from_template(SUMMARY_PROMPT)
    print(prompt_template)
    chain = prompt_template | summary_model
    summary = await chain.ainvoke(
        {"input_text": input_text, "summary": old_summary})

    return summary