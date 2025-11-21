# answer.py 

from google import genai
from google.genai import types


# ------------------------
client = genai.Client(api_key="AIzaSyDrIJQ3H69nXpU4dQ9yco7IQgCmZhCr9EU")





prompt = """
You are an intelligent explainer and guide.

Based on the following details:
- Question: {question}
- Answer type needed: {type}
- Context data: {data}

Please provide a natural, conversational answer that matches the requested answer type:

Answer Type Guidelines:
- "short": Provide a very brief, one-line factual answer
- "detailed": Give a comprehensive paragraph explanation with depth and context
- "list": Present information in a clear bullet-point or numbered list format
- "yes/no": Answer with yes or no, followed by a brief 1-sentence explanation if needed
- "definition": Provide a concise, clear definitional statement
- "step-by-step": Break down the information into sequential steps or instructions

Important:
- Use the context data provided to inform your answer
- Maintain a helpful, conversational tone as if you're personally explaining this to someone
- Don't simply copy the data text - rephrase and explain it in your own words
- Be accurate and informative while staying true to the requested format.
"""


def bot_answer(question, answer_type, history, data):
    
    
    

    # Generate response
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt.format(question=question, type=answer_type, data=data)
    )
    
    return resp.text


p="this is the answer {answer} this may be in english or hindi , so i want u to covert it into english stricty. The output must be in english language only word by word"


def english(answer):
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=p.format(answer=answer)
    )
    
    return resp.text
    
