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

class EmailWatcher:
    """A class for watching and processing job-related emails."""

    def __init__(self, email_address, password, inbox, imap_server):
        self.email_address = email_address
        self.password = password
        self.inbox = inbox
        self.imap_server = imap_server
        self.mail = None
        self.setup_logging()
        self.last_checked = self.load_last_checked_time()

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

    def connect(self):
        """
        Connect to the IMAP server.

        Returns:
            bool: True if connection is successful, False otherwise.
        """
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_server)
            self.mail.login(self.email_address, self.password)
            logging.info(f"Successfully connected to {self.imap_server}")
            return True
        except imaplib.IMAP4.error as e:
            logging.error(f"IMAP4 error: {e}")
            if "AUTHENTICATIONFAILED" in str(e):
                logging.error("Authentication failed. If using Gmail, please use an App Password.")
                logging.error("See: https://support.google.com/accounts/answer/185833")
            return False
        except Exception as e:
            logging.error(f"Error connecting to email server: {e}")
            return False

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

    def update_database(self, job_data):
        """
        Update the job application database with extracted information.

        Args:
            job_data (dict): Dictionary containing job application information.
        """
        conn = sqlite3.connect("job_applications.db")
        cursor = conn.cursor()

        try:
            # Check if the job already exists
            cursor.execute("SELECT id, status FROM jobs WHERE company = ? AND position = ?", (job_data["company"], job_data["position"]))
            existing_job = cursor.fetchone()

            if existing_job:
                # Update existing job
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
                    INSERT INTO jobs (company, position, status, application_date, last_updated, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (job_data["company"], job_data["position"], job_data["status"], job_data["date"], job_data["date"], job_data["notes"]))

            conn.commit()
            logging.info(f"Database updated for job: {job_data['company']} - {job_data['position']}")
        except sqlite3.Error as e:
            logging.error(f"Database error: {e}")
            conn.rollback()
        finally:
            conn.close()

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
    
    def interpret_email(self, email_data):
        """
        Interpret the email content to determine if it's job-related and extract information.

        Args:
            email_data (dict): Parsed email data.

        Returns:
            dict: Extracted job-related information or None if not job-related.
        """
        keywords = ["application", "interview", "offer", "rejection", "job", "position"]
        
        if any(keyword in email_data["subject"].lower() for keyword in keywords) or \
           any(keyword in email_data["body"].lower() for keyword in keywords):
            # Extract company name (this is a simple example and may need refinement)
            company_match = re.search(r"(?i)from\s+(.*?)\s", email_data["subject"])
            company = company_match.group(1) if company_match else "Unknown Company"
            
            # Determine status
            status = "Applied"
            if "interview" in email_data["subject"].lower() or "interview" in email_data["body"].lower():
                status = "Interview"
            elif "offer" in email_data["subject"].lower() or "offer" in email_data["body"].lower():
                status = "Offer"
            elif "reject" in email_data["subject"].lower() or "reject" in email_data["body"].lower():
                status = "Rejected"

            # Extract position (this is a simple example and may need refinement)
            position_match = re.search(r"(?i)for\s+(.*?)\s+position", email_data["subject"])
            position = position_match.group(1) if position_match else "Unknown Position"

            return {
                "company": company,
                "position": position,
                "status": status,
                "date": email_data["date"].strftime("%Y-%m-%d"),
                "notes": f"Email subject: {email_data['subject']}\n\nEmail body: {email_data['body'][:500]}..."
            }
        return None

    def run(self):
        """
        Main method to run the email watcher.

        This method connects to the email server, fetches new emails,
        interprets them, and updates the database with job-related information.
        """
        if self.connect():
            try:
                logging.info("Starting to fetch new emails")
                for email_message in self.fetch_new_emails():
                    logging.info("Processing a new email")
                    email_data = self.parse_email(email_message)
                    if email_data:
                        logging.info(f"Parsed email: Subject: {email_data['subject']}")
                        job_data = self.interpret_email(email_data)
                        if job_data:
                            logging.info(f"Interpreted job data: Company: {job_data['company']}, Position: {job_data['position']}, Status: {job_data['status']}")
                            self.update_database(job_data)
                        else:
                            logging.info("Email not interpreted as job-related")
                    else:
                        logging.warning("Failed to parse email")
                logging.info("Finished processing emails")
                self.save_last_checked_time()
            except Exception as e:
                logging.error(f"Error in email watcher run: {e}")
                raise  # Re-raise the exception to be caught in the main application
            finally:
                try:
                    self.mail.logout()
                    logging.info("Successfully logged out from email server")
                except Exception as e:
                    logging.error(f"Error during logout: {e}")
        else:
            logging.error("Failed to connect to email server")
            raise ConnectionError("Failed to connect to email server")