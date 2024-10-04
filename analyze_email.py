import os
from dotenv import load_dotenv
import openai

def analyze_email(email_content):
    # Load environment variables from .env file
    load_dotenv()

    # Initialize the OpenAI client with the API key
    client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    prompt = f"""
    Analyze the following email content and determine if it's related to a user's job application.

    The email must be a confirmation, rejection, interview invite, or offer from a company regarding a user's job application.
    An email from a service like Handshake that simply contains information about a job opening or a career fair or lists job postings is not considered a user's job application email. 
    
    If you determine the email is not related to a user's job application, respond with the following JSON exactly:
    {{
        "job_related": false,
        "company_name": "Unknown",
        "job_position": "Unknown",
        "application_status": "Unknown",
        "email_content": "Unknown"
    }}

    If you determine the email is related to a user's job application, extract the following information and respond with this JSON format:
    {{
        "job_related": true,
        "company_name": "String",
        "job_position": "String",
        "application_status": "String",
        "email_content": "String"
    }}

    For the job_position field only extract the job title, not the department, location, level, or any other information.
    For application_status, use only one of these values: "Applied", "Interview", "Offered", "Rejected".
    
    For email_content, include the entire email formatted as follows:
    - Remove or replace problematic characters like emojis or special characters
    - Preserve all original line breaks using \\n
    - Add an extra line break (\\n\\n) before and after the main body of the email
    - Do not return HTML or any other format, only plain text

    If you cannot determine any piece of information, use "Unknown" for that field.
    Ensure the JSON is valid and can be parsed directly. Do not include any markdown formatting or explanation outside the JSON object.

    Email content:
    {email_content}
    """

    completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are an AI assistant that analyzes emails and extracts job application information. You always and only respond with valid JSON."},
            {"role": "user", "content": prompt}
        ],
        model="gpt-4o-mini",
    )

    return completion.choices[0].message.content

# Example usage
# email_content = """"""
# result = parse_email(email_content)
# print(result)