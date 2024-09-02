import imaplib
import email
from email.header import decode_header
import datetime
import sqlite3
import re
import logging
import json
import os
import time
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import string
import hashlib
import backoff

nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('punkt_tab', quiet=True)

class EmailWatcher:
    """A class for watching and processing job-related emails."""

    def __init__(self, email_address, password, inbox, imap_server):
        self.connect_attempts = 0
        self.max_connect_attempts = 3
        self.email_address = email_address
        self.password = password
        self.inbox = inbox
        self.imap_server = imap_server
        self.mail = None
        self.setup_logging()
        self.last_checked = self.load_last_checked_time()
        self.stop_flag = False
        self.setup_nlp()
        self.setup_database()

    def setup_logging(self):
        """Configure logging for the EmailWatcher."""
        logging.basicConfig(filename='email_watcher.log', level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(message)s')

    def load_last_checked_time(self):
        """
        Load the last time emails were checked from a JSON file.

        Returns:
            datetime: The last checked time or 1 day ago if not available.
        """
        if os.path.exists('last_checked.json'):
            with open('last_checked.json', 'r') as f:
                data = json.load(f)
                return datetime.datetime.fromisoformat(data['last_checked'])
        return datetime.datetime.now() - datetime.timedelta(days=1)

    def save_last_checked_time(self):
        """Save the current time as the last checked time to a JSON file."""
        with open('last_checked.json', 'w') as f:
            json.dump({'last_checked': datetime.datetime.now().isoformat()}, f)

    @backoff.on_exception(backoff.expo, imaplib.IMAP4.error, max_tries=3)
    def connect(self):
        """Connect to the IMAP server with exponential backoff."""
        self.mail = imaplib.IMAP4_SSL(self.imap_server)
        self.mail.login(self.email_address, self.password)
        self.mail.select(self.inbox)
        logging.info(f"Successfully connected to {self.imap_server}")
        return True

    def setup_database(self):
        """Set up the database table for storing email IDs."""
        conn = sqlite3.connect("job_applications.db")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_emails (
                email_id TEXT PRIMARY KEY,
                job_id INTEGER,
                FOREIGN KEY (job_id) REFERENCES jobs (id)
            )
        """)
        conn.commit()
        conn.close()

    def fetch_new_emails(self):
        """
        Fetch new emails from the inbox since the last checked time.

        Yields:
            email.message.EmailMessage: Parsed email messages.
        """
        try:
            self.mail.select(self.inbox)
            date_string = self.last_checked.strftime("%d-%b-%Y")
            _, search_data = self.mail.search(None, f'(SINCE "{date_string}")')
            for num in search_data[0].split():
                try:
                    _, data = self.mail.fetch(num, '(RFC822)')
                    raw_email = data[0][1]
                    email_message = email.message_from_bytes(raw_email)
                    yield email_message
                except Exception as e:
                    logging.error(f"Error fetching email {num}: {e}")
        except imaplib.IMAP4.error as e:
            logging.error(f"IMAP4 error during fetch: {e}")
        except Exception as e:
            logging.error(f"Unexpected error during fetch: {e}")

    def parse_email(self, email_message):
        """
        Parse an email message and extract relevant information.

        Args:
            email_message (email.message.EmailMessage): The email message to parse.

        Returns:
            dict: Parsed email data including subject, sender, date, and body.
        """
        try:
            subject = self.decode_header(email_message.get("Subject", ""))
            sender = email.utils.parseaddr(email_message.get("From", ""))[1]
            date = email.utils.parsedate_to_datetime(email_message.get("Date"))

            body = ""
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_type() == "text/plain":
                        body = self.decode_payload(part)
                        break
            else:
                body = self.decode_payload(email_message)

            return {
                "subject": subject,
                "sender": sender,
                "date": date,
                "body": body
            }
        except Exception as e:
            logging.error(f"Error parsing email: {e}")
            return None

    def decode_header(self, header):
        """
        Decode email header.

        Args:
            header (str): The header to decode.

        Returns:
            str: Decoded header string.
        """
        try:
            decoded_header, encoding = decode_header(header)[0]
            if isinstance(decoded_header, bytes):
                return decoded_header.decode(encoding or 'utf-8', errors='replace')
            return decoded_header
        except Exception as e:
            logging.error(f"Error decoding header: {e}")
            return ""

    def decode_payload(self, part):
        """
        Decode email payload.

        Args:
            part (email.message.EmailMessage): The email part to decode.

        Returns:
            str: Decoded payload string.
        """
        try:
            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or 'utf-8'
            return payload.decode(charset, errors='replace')
        except Exception as e:
            logging.error(f"Error decoding payload: {e}")
            return ""
    
    def setup_nlp(self):
        """Set up NLP resources."""
        self.stop_words = set(stopwords.words('english'))
        self.punctuation = set(string.punctuation)
        self.job_keywords = {
            'application': ['application', 'applied', 'submit', 'consider'],
            'interview': ['interview', 'meet', 'discuss', 'conversation'],
            'offer': ['offer', 'congratulations', 'welcome', 'join'],
            'rejection': ['unfortunately', 'regret', 'not selected', 'other candidates', 'sorry']
        }

    def generate_email_id(self, email_message):
        """Generate a unique ID for an email."""
        # Use a combination of subject, sender, and date to create a unique ID
        subject = email_message.get("Subject", "")
        sender = email_message.get("From", "")
        date = email_message.get("Date", "")
        unique_string = f"{subject}{sender}{date}".encode('utf-8')
        return hashlib.md5(unique_string).hexdigest()

    def is_email_processed(self, email_id):
        """Check if an email has already been processed."""
        conn = sqlite3.connect("job_applications.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM processed_emails WHERE email_id = ?", (email_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def mark_email_as_processed(self, email_id, job_id):
        """Mark an email as processed in the database."""
        conn = sqlite3.connect("job_applications.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO processed_emails (email_id, job_id) VALUES (?, ?)", (email_id, job_id))
        conn.commit()
        conn.close()

    def preprocess_text(self, text):
        """Preprocess the text for NLP tasks."""
        tokens = word_tokenize(text.lower())
        tokens = [token for token in tokens if token not in self.stop_words and token not in self.punctuation]
        return tokens

    def extract_entities(self, text):
        """Extract company and position from the text."""
        company = "Unknown Company"
        position = "Unknown Position"

        company_patterns = [
            r"(?i)from\s+([\w\s&]+)",
            r"(?i)at\s+([\w\s&]+)",
            r"(?i)([\w\s&]+)\s+is hiring",
            r"(?i)join\s+([\w\s&]+)"
        ]
        for pattern in company_patterns:
            match = re.search(pattern, text)
            if match:
                company = match.group(1).strip()
                logging.debug(f"Extracted company: {company}")
                break

        position_patterns = [
            r"(?i)for\s+([\w\s-]+)\s+position",
            r"(?i)([\w\s-]+)\s+role",
            r"(?i)hiring\s+(?:a|an)\s+([\w\s-]+)",
            r"(?i)apply\s+for\s+([\w\s-]+)"
        ]
        for pattern in position_patterns:
            match = re.search(pattern, text)
            if match:
                position = match.group(1).strip()
                logging.debug(f"Extracted position: {position}")
                break

        return company, position

    def determine_email_type(self, tokens):
        """Determine the type of email based on keywords."""
        scores = {category: 0 for category in self.job_keywords}
        for token in tokens:
            for category, keywords in self.job_keywords.items():
                if token in keywords:
                    if category == "application":
                        scores[category] += 1
                    else:
                        scores[category] += 4
        email_type = max(scores, key=scores.get)
        logging.info(scores)
        logging.debug(f"Determined email type: {email_type}")
        return email_type

    def interpret_email(self, email_data, email_id):
        """
        Interpret the email content to determine if it's job-related and extract information.
        """
        subject_tokens = self.preprocess_text(email_data["subject"])
        logging.debug(f"Preprocessed subject tokens: {subject_tokens}")
        body_tokens = self.preprocess_text(email_data["body"])
        logging.debug(f"Preprocessed body tokens: {body_tokens}")
        all_tokens = subject_tokens + body_tokens

        job_related_score = sum(1 for token in all_tokens if any(token in keywords for keywords in self.job_keywords.values()))
        logging.debug(f"Job-related score: {job_related_score}")
        if job_related_score < 2:
            logging.info(f"Email {email_id} not considered job-related")
            return None

        company, position = self.extract_entities(email_data["subject"] + " " + email_data["body"])

        email_type = self.determine_email_type(all_tokens)
        status_map = {
            'application': 'Applied',
            'interview': 'Interview',
            'offer': 'Offer',
            'rejection': 'Rejected'
        }
        status = status_map.get(email_type, 'Applied')

        return {
            "email_id": email_id,
            "company": company,
            "position": position,
            "status": status,
            "date": email_data["date"].strftime("%Y-%m-%d"),
            "notes": f"Email type: {email_type}\nEmail subject: {email_data['subject']}\n\nEmail body: {email_data['body'][:500]}..."
        }

    def update_database(self, job_data):
        """Update the job application database with extracted information."""
        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                conn = sqlite3.connect("job_applications.db", timeout=10)
                cursor = conn.cursor()

                # Check if the job already exists
                cursor.execute("SELECT id, status, application_date FROM jobs WHERE company = ? AND position = ?", 
                               (job_data["company"], job_data["position"]))
                existing_job = cursor.fetchone()

                if existing_job:
                    job_id, current_status, existing_app_date = existing_job
                    if job_data["status"] != current_status:
                        cursor.execute("""
                            UPDATE jobs 
                            SET status = ?, last_updated = ?, notes = notes || '\n\n' || ?
                            WHERE id = ?
                        """, (job_data["status"], job_data["date"], job_data["notes"], job_id))
                else:
                    # Insert new job
                    cursor.execute("""
                        INSERT INTO jobs (company, position, status, application_date, last_updated, notes)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (job_data["company"], job_data["position"], job_data["status"], 
                          job_data["date"], job_data["date"], job_data["notes"]))
                    job_id = cursor.lastrowid

                # Mark the email as processed
                self.mark_email_as_processed(job_data["email_id"], job_id)

                conn.commit()
                logging.info(f"Database updated for job: {job_data['company']} - {job_data['position']}")
                break  # Success, exit the retry loop
            except sqlite3.Error as e:
                logging.error(f"Database error (attempt {attempt + 1}): {e}")
                if conn:
                    conn.rollback()
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    logging.error("Max retries reached. Failed to update database.")
            finally:
                if conn:
                    conn.close()

    def run(self):
        """Main method to run the email watcher."""
        try:
            if self.connect():
                logging.info("Starting to fetch new emails")
                for email_message in self.fetch_new_emails():
                    if self.stop_flag:
                        break
                    email_id = self.generate_email_id(email_message)
                    if not self.is_email_processed(email_id):
                        logging.info(f"Processing new email: {email_id}")
                        email_data = self.parse_email(email_message)
                        if email_data:
                            job_data = self.interpret_email(email_data, email_id)
                            if job_data:
                                self.update_database(job_data)
                            else:
                                logging.info("Email not interpreted as job-related")
                        else:
                            logging.warning("Failed to parse email")
                    else:
                        logging.info(f"Email already processed: {email_id}")
                logging.info("Finished processing emails")
                self.save_last_checked_time()
        except imaplib.IMAP4.error as e:
            logging.error(f"IMAP4 error: {e}")
        except ConnectionError as e:
            logging.error(f"Connection error: {e}")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
        finally:
            if self.mail:
                try:
                    self.mail.logout()
                    logging.info("Successfully logged out from email server")
                except Exception as e:
                    logging.error(f"Error during logout: {e}")