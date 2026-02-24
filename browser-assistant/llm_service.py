import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

llm = ChatGroq(
    model_name="llama-3.1-8b-instant",
)

prompt = ChatPromptTemplate.from_template("""
You are an AI assistant helping user understand a webpage.

Current Webpage Content:
------------------------
{context}

User Question:
{question}

Answer clearly and accurately based ONLY on the page content.
""")

def get_answer(context: str, question: str) -> str:
    chain = prompt | llm
    response = chain.invoke({
        "context": context,  # avoid overflow
        "question": question
    })
    return response.content