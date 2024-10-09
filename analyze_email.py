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
    An email from a service like Handshake that contains information about a job opening or a career fair or asks the user to apply or lists job postings is not considered a user's job application email. 

    
    If you determine the email is not related to a user's job application, respond with the following JSON exactly:
    {{
        "company_name": null,
        "job_position": null,
        "application_status": null,
        "email_content": null
    }}

    If you determine the email is related to a user's job application, extract the following information and respond with this JSON format:
    {{
        "company_name": String,
        "job_position": String,
        "application_status": String,
        "email_content": String
    }}

    For the job_position field only extract the job title, not the department, location, level, or any other information.
    Ensure the job_position is set to a real job title, not a generic term like "internship" or "job" or something that is not a job title.
    For application_status, use only one of these values: "Applied", "Interview", "Offered", "Rejected".
    If a job-related email mentions completing an assessment, set the application_status to "Applied".
    
    For email_content, format the body's content in a standardized way as follows:
    - Remove or replace problematic characters like emojis or special characters
    - Add line breaks between all sentences using \\n
    - Add an extra line break (\\n\\n) before and after the main body of the email
    - Do not indent anything (no extra spaces at the beginning of lines)
    - Do not return HTML or any other format, only plain text

    If the email is not related to a job application, make sure all fields are set to null.
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