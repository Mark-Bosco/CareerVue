import imaplib
import email
from email.header import decode_header
import sqlite3
import logging
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
import string
import backoff
from collections import Counter

nltk.download("punkt", quiet=True)
nltk.download("stopwords", quiet=True)
nltk.download("punkt_tab", quiet=True)
nltk.download("averaged_perceptron_tagger", quiet=True)
nltk.download("averaged_perceptron_tagger_eng", quiet=True)

class EmailWatcher:
    """A class for watching and processing job-related emails."""

    def __init__(self, email_address, password, inbox, imap_server):
        """Initialize the EmailWatcher with email settings."""
        self.connect_attempts = 0
        self.max_connect_attempts = 3
        self.email_address = email_address
        self.password = password
        self.inbox = inbox
        self.imap_server = imap_server
        self.mail = None
        self.stop_flag = False
        self.setup_nlp()

    @backoff.on_exception(backoff.expo, imaplib.IMAP4.error, max_tries=3)
    def connect(self):
        """Connect to the IMAP server with exponential backoff."""
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_server)
            self.mail.login(self.email_address, self.password)
            self.mail.select(self.inbox)
            logging.debug(f"Successfully connected to {self.imap_server}")
            return True
        except imaplib.IMAP4.error as e:
            logging.error(f"Error connecting to {self.imap_server}: {e}")
            return False

    def fetch_new_emails(self, last_checked):
        """Fetch new emails from the inbox since the last checked time."""
        try:
            self.mail.select(self.inbox)
            date_string = last_checked.strftime("%d-%b-%Y")
            _, search_data = self.mail.search(None, f'(SINCE "{date_string}")')
            for num in search_data[0].split():
                try:
                    _, data = self.mail.fetch(num, '(RFC822)')
                    raw_email = data[0][1]
                    email_message = email.message_from_bytes(raw_email)
                    yield num, email_message
                except Exception as e:
                    logging.error(f"Error fetching email {num}: {e}")
        except imaplib.IMAP4.error as e:
            logging.error(f"IMAP4 error during fetch: {e}")
        except Exception as e:
            logging.error(f"Unexpected error during fetch: {e}")

    def parse_email(self, email_message):
        """Parse an email message and extract relevant information."""
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

            return {"subject": subject, "sender": sender, "date": date, "body": body}
        except Exception as e:
            logging.error(f"Error parsing email: {e}")
            return None

    def decode_header(self, header):
        """Decode email header."""
        try:
            decoded_header, encoding = decode_header(header)[0]
            if isinstance(decoded_header, bytes):
                return decoded_header.decode(encoding or "utf-8", errors="replace")
            return decoded_header
        except Exception as e:
            logging.error(f"Error decoding header: {e}")
            return ""

    def decode_payload(self, part):
        """Decode email payload."""
        try:
            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
        except Exception as e:
            logging.error(f"Error decoding payload: {e}")
            return ""

    def setup_nlp(self):
        """Set up NLP resources."""
        self.stop_words = set(stopwords.words("english"))
        self.punctuation = set(string.punctuation)

        # Define keywords for different types of job-related emails
        self.job_keywords = {
            "application": ["application", "applied", "consider", "job", "opening", "position", "role", "resume", "cv",],
            "interview": ["interview", "meet", "conversation", "call", "schedule", "talk", "chat", "screen", "assessment",],
            "offer": ["offer", "congratulations", "welcome", "join", "hired","contract", "role", "start",],
            "rejection": ["unfortunately", "regret", "other", "candidates", "sorry", "qualified", "experience", "skills", "background",],
        }
        
        # Define keywords for different types of job-related emails
        self.position_keywords = [
            "Software Engineer", "Data Scientist", "Machine Learning Engineer",
            "Web Developer", "Mobile App Developer", "Systems Analyst",
            "Database Administrator", "Cloud Engineer", "DevOps Engineer",
            "Cybersecurity Analyst", "Full Stack Developer", "Frontend Developer",
            "Backend Developer", "UI/UX Designer", "Network Engineer",
            "AI Engineer", "Business Intelligence Analyst", "Game Developer",
            "Embedded Systems Engineer", "Data Engineer", "IT Support Specialist",
            "Technical Project Manager", "QA Engineer", "Quality Assurance Engineer",
            "Site Reliability Engineer", "Software Architect", "Solutions Architect",
            "Product Manager", "Scrum Master", "Agile Coach", "Data Analyst",
            "Business Analyst", "Systems Administrator", "Network Administrator",
            "Information Security Analyst", "Cloud Architect", "Big Data Engineer",
            "Blockchain Developer", "IoT Developer", "AR/VR Developer",
            "Technical Writer", "IT Consultant", "Technology Consultant"
        ]

        # Define common company suffixes
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

        email_type = self.extract_email_type(tokens)
        position = self.extract_position(email_data)
        company = self.extract_company(email_data)

        logging.debug(f"Determined email type: {email_type}")
        logging.debug(f"Determined position: {position}")
        logging.debug(f"Determined company: {company}")

        return email_type, position, company

    def extract_email_type(self, tokens):
        type_scores = {category: 0 for category in self.job_keywords}

        # Score email type
        for token in tokens:
            for category, keywords in self.job_keywords.items():
                if token in keywords:
                    if category == "application":
                        type_scores[category] += 1
                    else:
                        type_scores[category] += 4

        return max(type_scores, key=type_scores.get)

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
            if tag.startswith("NNP"):
                # Check for multi-word company names
                company_name = word
                j = i + 1
                while j < len(pos_tags) and pos_tags[j][1].startswith("NNP"):
                    company_name += f" {pos_tags[j][0]}"
                    j += 1
                potential_companies.append(company_name)

        # Score potential company names
        company_scores = Counter()
        for company in potential_companies:
            score = 1
            # Boost score for companies with common suffixes
            if any(
                suffix in company.split() for suffix in self.common_company_suffixes
            ):
                score += 2
            # Boost score for companies mentioned multiple times
            company_scores[company] += score

        # Get the most likely company name
        if company_scores:
            most_likely_company = company_scores.most_common(1)[0][0]
            logging.debug(f"Extracted company name: {most_likely_company}")
            return most_likely_company
        else:
            logging.warning("No company name extracted")
            return "Unknown"

    def extract_position(self, email_data):
        """Extract the job position from the email data."""
        full_text = f"{email_data['subject']} {email_data['body']}"
        sentences = sent_tokenize(full_text)

        # Function to check if a position is in a sentence
        def position_in_sentence(position, sentence):
            return position.lower() in sentence.lower()

        # First, try to find an exact match
        for position in self.position_keywords:
            if any(position_in_sentence(position, sentence) for sentence in sentences):
                return position

        # If no exact match, try to find partial matches
        words = word_tokenize(full_text.lower())
        bigrams = list(nltk.bigrams(words))
        trigrams = list(nltk.trigrams(words))

        position_scores = Counter()

        for position in self.position_keywords:
            position_lower = position.lower()
            position_words = position_lower.split()

            # Check for full position match in bigrams and trigrams
            if len(position_words) == 2:
                position_scores[position] += bigrams.count(tuple(position_words))
            elif len(position_words) == 3:
                position_scores[position] += trigrams.count(tuple(position_words))

            # Check for partial matches
            for i in range(len(position_words)):
                for j in range(i + 1, len(position_words) + 1):
                    partial = " ".join(position_words[i:j])
                    position_scores[position] += words.count(partial)

        # Get the position with the highest score
        if position_scores:
            best_position = max(position_scores, key=position_scores.get)
            if position_scores[best_position] > 0:
                return best_position

        return "Unknown Position"

    def interpret_email(self, email_data):
        """Interpret the email content to determine if it's job-related and extract information."""
        subject_tokens = self.preprocess_text(email_data["subject"])
        body_tokens = self.preprocess_text(email_data["body"])
        all_tokens = subject_tokens + body_tokens

        job_related_score = sum(1 for token in all_tokens if any(token in keywords for keywords in self.job_keywords.values()))
        if job_related_score <= 5:
            return None

        email_type, position, company = self.determine_entities(all_tokens, email_data)

        status_map = {
            'application': 'Applied',
            'interview': 'Interview',
            'offer': 'Offer',
            'rejection': 'Rejected'
        }
        status = status_map.get(email_type, "Applied")

        return {
            "company": company,
            "position": position,
            "status": status,
            "date": email_data["date"].strftime("%Y-%m-%d"),
            "notes": f"Email subject: {email_data['subject']}\n\nEmail body: {email_data['body'][:500]}...",
        }

    @backoff.on_exception(backoff.expo, sqlite3.Error, max_tries=3)
    def update_database(self, job_data):
        """Update the job application database with extracted information."""
        try:
            conn = sqlite3.connect("job_applications.db", timeout=10)
            cursor = conn.cursor()

            # Check if the job already exists based on NLP-extracted company and position
            cursor.execute("""
                SELECT id, status, is_deleted, company, position 
                FROM jobs 
                WHERE nlp_company = ? AND nlp_position = ?
            """, (job_data["company"], job_data["position"]))
            existing_job = cursor.fetchone()

            if existing_job:
                job_id, current_status, is_deleted, current_company, current_position = existing_job

                if is_deleted:
                    logging.debug(f"Job {job_data['company']} - {job_data['position']} was previously deleted. Skipping update.")
                    return
            
                if job_data["status"] != current_status:
                    cursor.execute("""
                        UPDATE jobs 
                        SET status = ?, last_updated = ?, notes = notes || '\n\n' || ?, updated = 1,
                            nlp_company = ?, nlp_position = ?
                        WHERE id = ?
                    """, (job_data["status"], job_data["date"], job_data["notes"], 
                          job_data["company"], job_data["position"], job_id))
                else:
                    cursor.execute("""
                        UPDATE jobs 
                        SET last_updated = ?, notes = notes || '\n\n' || ?,
                            nlp_company = ?, nlp_position = ?
                        WHERE id = ?
                    """, (job_data["date"], job_data["notes"], 
                          job_data["company"], job_data["position"], job_id))
                
                logging.debug(f"Updated existing job: {current_company} - {current_position}")
            else:
                # Insert new job
                cursor.execute("""
                    INSERT INTO jobs (company, position, status, application_date, last_updated, notes, updated, is_deleted, nlp_company, nlp_position) 
                    VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?, ?)
                """, (job_data["company"], job_data["position"], job_data["status"], job_data["date"], 
                      job_data["date"], job_data["notes"], job_data["company"], job_data["position"]))
                job_id = cursor.lastrowid
                logging.debug(f"Inserted new job: {job_data['company']} - {job_data['position']}")

            conn.commit()
            logging.debug(f"Database updated for job: {job_data['company']} - {job_data['position']}")
        except sqlite3.Error as e:
            logging.error(f"Database error: {e}")
            if conn:
                conn.rollback()
            raise  # Re-raise exception for backoff to handle retries
        finally:
            if conn:
                conn.close()


    def process_email(self, email_id, email_message):
        """Process a single email message."""
        email_data = self.parse_email(email_message)
        if email_data:
            job_data = self.interpret_email(email_data)
            if job_data:
                self.update_database(job_data)
            else:
                logging.debug(f"Email {email_id} not interpreted as job-related")
        else:
            logging.warning(f"Failed to parse email {email_id}")

    def run(self, last_checked):
        """Main method to run the email watcher."""
        try:
            if self.connect():
                logging.debug(f"Starting to fetch new emails since {last_checked}")
                for email_id, email_message in self.fetch_new_emails(last_checked):
                    if self.stop_flag:
                        break
                    self.process_email(email_id, email_message)
                logging.debug("Finished processing emails")
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
                    logging.debug("Successfully logged out from email server")
                except Exception as e:
                    logging.error(f"Error during logout: {e}")
