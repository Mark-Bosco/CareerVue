import hashlib
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
import backoff
from collections import Counter

nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('punkt_tab', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)
nltk.download('averaged_perceptron_tagger_eng', quiet=True)

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
        self.processed_hashes = set()
        self.load_processed_hashes()

    def load_processed_hashes(self):
        """Load all processed email hashes from the database."""
        conn = sqlite3.connect("job_applications.db")
        cursor = conn.cursor()
        cursor.execute("SELECT email_hash FROM jobs")
        hashes = cursor.fetchall()
        conn.close()
        self.processed_hashes = set(hash[0] for hash in hashes)
        logging.info(f"Loaded {len(self.processed_hashes)} processed email hashes")

    def remove_processed_hash(self, email_hash):
        """Remove a processed hash from the cache."""
        if email_hash in self.processed_hashes:
            self.processed_hashes.remove(email_hash)
            logging.info(f"Removed hash {email_hash} from processed hashes")
        else:
            logging.warning(f"Attempted to remove non-existent hash {email_hash} from processed hashes")
            
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
        self.position_keywords = {
            "Engineer": ["software", "systems", "data", "frontend", "backend", "full stack", "devops", "cloud", "machine learning", "ai"],
            "Developer": ["web", "mobile", "app", "frontend", "backend", "full stack", "software"],
            "Analyst": ["data", "business", "financial", "systems", "security"],
            "Manager": ["project", "product", "technical", "engineering", "program"],
            "Designer": ["ui", "ux", "user interface", "user experience", "graphic"],
            "Scientist": ["data", "research", "machine learning"],
            "Administrator": ["system", "database", "network"],
            "Architect": ["software", "systems", "solutions", "enterprise", "data"],
            "Specialist": ["it", "security", "support", "qa", "quality assurance"],
            "Consultant": ["it", "technology", "software", "management"],
            "Intern": ["software", "data", "engineering", "research"]
        }
        self.common_company_suffixes = [
            "Inc", "LLC", "Ltd", "Limited", "Corp", "Corporation", "Co", "Company",
            "GmbH", "AG", "SA", "NV", "PLC", "Group", "Holdings", "Ventures"
        ]

    def preprocess_text(self, text):
        """Preprocess the text for NLP tasks."""
        tokens = word_tokenize(text.lower())
        tokens = [token for token in tokens if token not in self.stop_words and token not in self.punctuation]
        return tokens

    def determine_entities(self, tokens, email_data):
        """Determine the type of email and position based on keywords."""
        type_scores = {category: 0 for category in self.job_keywords}
        position_scores = Counter()

        # Combine tokens from subject and body
        all_text = f"{email_data['subject']} {email_data['body']}"
        all_tokens = word_tokenize(all_text.lower())

        # Score email type
        for token in tokens:
            for category, keywords in self.job_keywords.items():
                if token in keywords:
                    if category == "application":
                        type_scores[category] += 1
                    else:
                        type_scores[category] += 4

        # Score positions
        for i in range(len(all_tokens) - 1):
            bigram = f"{all_tokens[i]} {all_tokens[i+1]}"
            for position, keywords in self.position_keywords.items():
                if all_tokens[i] in keywords or bigram in keywords:
                    position_scores[position] += 1

        email_type = max(type_scores, key=type_scores.get)
        
        # Determine the most likely position
        if position_scores:
            position = position_scores.most_common(1)[0][0]
        else:
            position = "Unknown"

        logging.info(f"Type scores: {type_scores}")
        logging.info(f"Position scores: {position_scores}")
        logging.debug(f"Determined email type: {email_type}")
        logging.debug(f"Determined position: {position}")

        return email_type, position

    def extract_company(self, email_data):
        """Extract the company name from the email data."""
        # Combine subject and body for analysis
        full_text = f"{email_data['subject']} {email_data['body']}"
        
        # Tokenize and tag parts of speech
        tokens = word_tokenize(full_text)
        pos_tags = nltk.pos_tag(tokens)

        # Extract potential company names (proper nouns)
        potential_companies = []
        for i, (word, tag) in enumerate(pos_tags):
            if tag.startswith('NNP'):
                # Check for multi-word company names
                company_name = word
                j = i + 1
                while j < len(pos_tags) and pos_tags[j][1].startswith('NNP'):
                    company_name += f" {pos_tags[j][0]}"
                    j += 1
                potential_companies.append(company_name)

        # Score potential company names
        company_scores = Counter()
        for company in potential_companies:
            score = 1
            # Boost score for companies with common suffixes
            if any(suffix in company.split() for suffix in self.common_company_suffixes):
                score += 2
            # Boost score for companies mentioned multiple times
            company_scores[company] += score

        # Get the most likely company name
        if company_scores:
            most_likely_company = company_scores.most_common(1)[0][0]
            logging.info(f"Extracted company name: {most_likely_company}")
            return most_likely_company
        else:
            logging.warning("No company name extracted")
            return "Unknown"

    def generate_email_hash(self, email_data):
        """Generate a unique hash for an email."""
        hash_input = f"{email_data['subject']}{email_data['sender']}{email_data['date']}"
        return hashlib.md5(hash_input.encode()).hexdigest()

    def is_email_processed(self, email_hash):
        """Check if an email has already been processed."""
        return email_hash in self.processed_hashes

    def process_email(self, email_message):
        """Process a single email message."""
        email_data = self.parse_email(email_message)
        if email_data:
            email_hash = self.generate_email_hash(email_data)
            if not self.is_email_processed(email_hash):
                job_data = self.interpret_email(email_data, email_hash)
                if job_data:
                    self.update_database(job_data)
                    self.processed_hashes.add(email_hash)
                else:
                    logging.info("Email not interpreted as job-related")
            else:
                logging.info(f"Email with hash {email_hash} has already been processed")
        else:
            logging.warning("Failed to parse email")

    def interpret_email(self, email_data, email_hash):
        """
        Interpret the email content to determine if it's job-related and extract information.
        """
        subject_tokens = self.preprocess_text(email_data["subject"])
        body_tokens = self.preprocess_text(email_data["body"])
        all_tokens = subject_tokens + body_tokens

        job_related_score = sum(1 for token in all_tokens if any(token in keywords for keywords in self.job_keywords.values()))
        logging.debug(f"Job-related score: {job_related_score}")
        if job_related_score < 2:
            logging.info(f"Email not considered job-related")
            return None

        email_type, position = self.determine_entities(all_tokens, email_data)
        company = self.extract_company(email_data)
        
        status_map = {
            'application': 'Applied',
            'interview': 'Interview',
            'offer': 'Offer',
            'rejection': 'Rejected'
        }
        status = status_map.get(email_type, 'Applied')

        return {
            "company": company,
            "position": position,
            "status": status,
            "date": email_data["date"].strftime("%Y-%m-%d"),
            "notes": f"Email subject: {email_data['subject']}\n\nEmail body: {email_data['body'][:500]}...",
            "email_hash": email_hash
        }

    def update_database(self, job_data):
        """Update the job application database with extracted information."""
        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                conn = sqlite3.connect("job_applications.db", timeout=10)
                cursor = conn.cursor()

                # Check if the job already exists based on email_hash
                cursor.execute("SELECT id, status FROM jobs WHERE email_hash = ?", (job_data["email_hash"],))
                existing_job = cursor.fetchone()

                if existing_job:
                    job_id, current_status = existing_job
                    if job_data["status"] != current_status:
                        cursor.execute("""
                            UPDATE jobs 
                            SET status = ?, last_updated = ?, notes = notes || '\n\n' || ?
                            WHERE id = ?
                        """, (job_data["status"], job_data["date"], job_data["notes"], job_id))
                else:
                    # Insert new job
                    cursor.execute("""
                        INSERT INTO jobs (company, position, status, application_date, last_updated, notes, email_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (job_data["company"], job_data["position"], job_data["status"], 
                          job_data["date"], job_data["date"], job_data["notes"], job_data["email_hash"]))
                    job_id = cursor.lastrowid

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
                    self.process_email(email_message)
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