import logging
import time
import customtkinter as ctk
import sqlite3
from CTkMessagebox import CTkMessagebox
from datetime import datetime, timedelta
import threading
import json
import os
from email_watcher import EmailWatcher
from notes_window import NotesWindow
from email_config_dialog import EmailConfigDialog
import database_setup

# Suppress PIL debug messages
logging.getLogger('PIL').setLevel(logging.WARNING)

class HomeScreen(ctk.CTk):
    """The main application window for the job tracker."""

    def __init__(self):
        """Initialize the main application window."""
        super().__init__()

        # Delete old log file to start fresh
        if os.path.exists("careervue.log"):
            try:
                os.remove("careervue.log")
            except Exception as e:
                print(f"Error deleting log file 'careervue.log': {e}")
        else:
            print(f"Log file 'careervue.log' does not exist.")

        # Set up logging
        self.setup_logging()

        # Create database if it does not exist
        if not os.path.exists("job_applications.db"):
            database_setup.main()
            logging.info("Database created successfully.")

        # Set up main window title and size
        self.title("CareerVue - Job Application Tracker")
        self.geometry("1200x600")

        # Configure main grid
        self.grid_columnconfigure(
            0, weight=1
        )  # Allow main frame to expand horizontally
        self.grid_rowconfigure(1, weight=1)  # Allow jobs frame to expand vertically

        # Initialize variables
        self.job_rows = {}  # Dictionary to store job rows by job ID
        self.next_row = 1  # Start job rows from row 1 (after headers)
        self.email_watcher = None
        self.email_watcher_thread = None

        # Set up UI components
        logging.info("Setting up UI components.")
        self.setup_header_frame()
        self.setup_main_frame()
        self.setup_jobs_frame()

        # Load email configuration
        self.config = self.load_config()
        if self.config == {}:
            logging.info("No email configuration found. Opening email config dialog.")
            self.open_email_config()

        # Start email watcher
        logging.info("Starting email watcher.")
        self.start_email_watcher()

        # Refresh job list
        logging.info("Refreshing job list.")
        self.refresh_jobs()

    def setup_logging(self):
        """Configure logging for the app."""
        logging.basicConfig(
            filename="careervue.log",
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )

    def setup_header_frame(self):
        """Set up the header frame with logo, add button, and refresh button."""
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=10) 
        self.top_frame.grid_columnconfigure(1, weight=1) 

        # Add logo label
        self.logo_label = ctk.CTkLabel(
            self.top_frame, text="CareerVue", font=ctk.CTkFont(size=24, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        # Add button for email configuration
        self.email_config_button = ctk.CTkButton(
            self.top_frame, text="Add Email Config", command=self.open_email_config
        )
        self.email_config_button.grid(row=0, column=1, padx=10, pady=10)

        # Add refresh button
        self.refresh_button = ctk.CTkButton(
            self.top_frame,
            text="Refresh",
            width=40,
            font=("Arial", 14),
            command=self.refresh_emails_and_jobs,
        )
        self.refresh_button.grid(row=0, column=2, padx=10, pady=10, sticky="e")

        # Add button to add new job
        self.add_job_button = ctk.CTkButton(
            self.top_frame,
            text="+",
            width=40,
            font=("Arial", 20),
            command=self.add_new_job,
        )
        self.add_job_button.grid(row=0, column=3, padx=10, pady=10, sticky="e")

        # Add last sync time label
        self.last_sync_label = ctk.CTkLabel(
            self.top_frame, text="Last sync: Never", font=("Arial", 12)
        )
        self.last_sync_label.grid(
            row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="w"
        )

        # Add email watcher status indicator
        self.status_indicator = ctk.CTkLabel(
            self.top_frame,
            text="Connection Status",
            font=("Arial", 20),
            text_color="red",
        )
        self.status_indicator.grid(row=1, column=2, padx=10, pady=(0, 10), sticky="e")

    def update_sync_time(self):
        """Update the last sync time label and save the time to a file."""
        current_time = datetime.now()
        self.last_sync_label.configure(text=f"Last sync: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Save the current time to a file
        with open('last_checked.json', 'w') as f:
            json.dump({'last_checked': current_time.isoformat()}, f)
        
        logging.info(f"Last sync time updated to {current_time}")

    def setup_main_frame(self):
        """Set up the main frame that will contain the jobs list."""
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

    def setup_jobs_frame(self):
        """Set up the scrollable frame for job entries and headers."""
        self.jobs_frame = ctk.CTkScrollableFrame(self.main_frame)
        self.jobs_frame.grid(row=0, column=0, sticky="nsew")
        self.jobs_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        # Set fixed width for Notes and Delete columns
        self.jobs_frame.grid_columnconfigure((5, 6), weight=0)

        headers = ["Company","Position","Status","Application Date","Last Updated","",""]
        # Create header labels 
        for i, header in enumerate(headers):
            label = ctk.CTkLabel(self.jobs_frame, text=header, font=ctk.CTkFont(size=16, weight="bold"))
            label.grid(row=0, column=i, padx=5, pady=(5, 10), sticky="ew")
            # Center text for all columns except Notes and Delete
            if i < 5:  
                label.configure(anchor="center")

    def refresh_emails_and_jobs(self):
        """Refresh emails and update the job list."""
        if self.email_watcher:
            try:
                # Get the last checked time
                last_checked = self.load_sync_time()
                # Manually run email watcher
                self.email_watcher.run(last_checked)
                self.refresh_jobs()
                self.update_sync_time()
                self.status_indicator.configure(text_color="green")
                CTkMessagebox(title="Success", message="Emails checked and jobs refreshed!", icon="info")
            except Exception as e:
                logging.error(f"An error occurred while refreshing emails: {e}")
                self.status_indicator.configure(text_color="red")
                CTkMessagebox(title="Error", message=f"Failed to refresh emails: {str(e)}. Please try again.", icon="cancel")
        else:
            self.status_indicator.configure(text_color="red")
            CTkMessagebox(title="Error", message="Email watcher not configured. Please set up email configuration first.", icon="cancel")

    def load_config(self):
        """Load the email configuration from the config file."""
        try:
            with open("email_config.json", "r") as f:
                config = json.load(f)
                logging.info("Email configuration loaded successfully.")
        except FileNotFoundError:
            logging.warning("email_config.json not found.")
            config = {}
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            config = {}

        return config

    def update_config(self, new_config):
        """Update the email configuration and restart the email watcher."""
        logging.info("Updating email configuration.")
        self.config = new_config
        if self.email_watcher:
            self.stop_email_watcher()
        self.start_email_watcher()

    def start_email_watcher(self):
        """Start the email watcher thread."""
        if not self.config:
            return

        required_keys = ["email", "password", "inbox", "imap_server"]
        if not all(key in self.config for key in required_keys):
            CTkMessagebox(title="Error",message="Email configuration incomplete. Please check your credentials and try again",icon="cancel")
            logging.error("Email configuration incomplete. Cannot start email watcher.")
            return

        # Create the email watcher object
        self.email_watcher = EmailWatcher(self.config["email"], self.config["password"], self.config["inbox"], self.config["imap_server"])

        # Test connection before starting the thread
        if self.email_watcher.connect():
            self.email_watcher_thread = threading.Thread(target=self.run_email_watcher, daemon=True)
            self.email_watcher_thread.start()
            self.status_indicator.configure(text_color="green")
            logging.info("Started email watcher thread.")
        else:
            self.status_indicator.configure(text_color="red")
            CTkMessagebox(title="Error",message="Failed to connect to email server. Please check your credentials and try again.",icon="cancel")
            logging.error("Failed to connect to email server. Email watcher not started.")

    def run_email_watcher(self):
        """Run the email watcher continuously."""
        while not getattr(self.email_watcher, "stop_flag", False):
            try:
                logging.info("Running email watcher")
                last_checked = self.load_sync_time()
                self.email_watcher.run(last_checked)
                self.after(0, self.update_sync_time)
                self.after(0, self.refresh_jobs)
                self.after(0, self.status_indicator.configure(text_color="green"))
            except Exception as e:
                logging.error(f"An error occurred: {e}")
                self.after(0, self.status_indicator.configure(text_color="red"))
            finally:
                # Sleep for 10 minutes before checking again
                time.sleep(600)
        
    def load_sync_time(self):
        """Get the last checked time from the file."""
        try:
            with open('last_checked.json', 'r') as f:
                data = json.load(f)
                return datetime.fromisoformat(data['last_checked']) - timedelta(days=1)
        except (FileNotFoundError, json.JSONDecodeError):
            # Default to 1 day ago if no last checked time is found or if there's an error
            return datetime.now() - timedelta(days=1)

    def stop_email_watcher(self):
        """Stop the current email watcher thread."""
        if (self.email_watcher and self.email_watcher_thread and self.email_watcher_thread.is_alive()):
            self.email_watcher.stop_flag = True
            # Wait for the thread to finish
            self.email_watcher_thread.join(timeout=5)  
        self.email_watcher = None
        self.email_watcher_thread = None

    def add_new_job(self):
        """Add a new job entry to the database and UI."""
        conn = sqlite3.connect("job_applications.db")
        cursor = conn.cursor()
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        cursor.execute(
            """INSERT INTO jobs (company, position, status, application_date, last_updated, notes, updated) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("New Company", "New Position","Applied", current_date, current_date, "", 0,)
        )

        job_id = cursor.lastrowid
        conn.commit()
        conn.close()

        self.add_job_row(job_id, "New Company", "New Position", "Applied", current_date, current_date, "", 0)
        logging.info(f"Added new job with ID {job_id}")

    def delete_job(self, job_id):
        """Delete a job entry from the database and UI."""
        confirm = CTkMessagebox(title="Confirm Deletion",message="Are you sure you want to delete this job?", icon="question", option_1="Yes", option_2="No")

        if confirm.get() == "Yes":
            conn = sqlite3.connect("job_applications.db")
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            result = cursor.fetchone()

            if result:
                # Delete the job from the database
                cursor.execute("DELETE FROM jobs WHERE id=?", (job_id,))
                conn.commit()
                # Remove the job row from the UI
                self.remove_job_row(job_id)
                logging.info(f"Deleted job with ID {job_id}")
            else:
                logging.warning(f"Attempted to delete non-existent job with ID {job_id}")

            conn.close()

    def validate_and_update(self, job_id, field, value, widget):
        """Validate user input and update the job if valid."""
        error = None
        if field in ["company", "position"] and not value.strip():
            error = f"{field.capitalize()} cannot be empty."
        elif field == "application_date":
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                error = "Invalid date. Please use YYYY-MM-DD format."

        if error:
            CTkMessagebox(title="Validation Error", message=error, icon="cancel")
            widget.delete(0, ctk.END)
            widget.insert(0, self.get_original_value(job_id, field))
        else:
            self.update_job(job_id, field, value)
            logging.info(f"Updated job {job_id} field {field} to {value}")

    def get_original_value(self, job_id, field):
        """Retrieve the original value of a field from the database."""
        conn = sqlite3.connect("job_applications.db")
        cursor = conn.cursor()
        cursor.execute(f"SELECT {field} FROM jobs WHERE id = ?", (job_id,))
        value = cursor.fetchone()[0]
        conn.close()
        return value

    def update_job(self, job_id, field, value):
        """Update a job field in the database and UI."""
        conn = sqlite3.connect("job_applications.db")
        cursor = conn.cursor()
        try:
            current_date = datetime.now().strftime("%Y-%m-%d")
            cursor.execute(f"UPDATE jobs SET {field} = ?, last_updated = ? WHERE id = ?", (value, current_date, job_id))
            conn.commit()
            self.update_job_row(job_id, field, value)
            if field != "notes":
                self.update_job_row(job_id, "last_updated", current_date)
            logging.info(f"Updated job {job_id} field {field} to {value}")
        except sqlite3.Error as e:
            logging.error(f"An error occurred while updating the job: {e}")
            CTkMessagebox(title="Database Error", message="An error occurred while updating the job.", icon="cancel")
        finally:
            conn.close()

    def open_notes(self, job_id, notes):
        """Open the notes window for a specific job."""
        NotesWindow(self, job_id, notes)

    def refresh_jobs(self):
        """Refresh the job list from the database."""
        conn = sqlite3.connect("job_applications.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs ORDER BY last_updated DESC")
        jobs = cursor.fetchall()
        conn.close()

        # Set of current job IDs 
        existing_job_ids = set(self.job_rows.keys())

        for job in jobs:
            (job_id, company, position, status, app_date, last_updated, notes, updated) = job
            if job_id not in self.job_rows:
                self.add_job_row(job_id, company, position, status, app_date, last_updated, notes, updated)
                logging.info(f"Added job with ID {job_id}")
            else:
                self.update_job_row(job_id, "company", company)
                self.update_job_row(job_id, "position", position)
                self.update_job_row(job_id, "status", status)
                self.update_job_row(job_id, "application_date", app_date)
                self.update_job_row(job_id, "last_updated", last_updated)
                self.update_job_row(job_id, "updated", updated)
                logging.info(f"Updated job with ID {job_id}")
            # Once added or updated, remove from set
            existing_job_ids.discard(job_id)

        # Remove any leftover jobs
        for job_id in existing_job_ids:
            logging.info(f"Removing job with ID {job_id}")
            self.remove_job_row(job_id)
        
        logging.info("Job list refreshed.")
        self.update_sync_time()

    def add_job_row(self, job_id, company, position, status, app_date, last_updated, notes, updated):
        """Add a new job row to the UI."""
        row = self.next_row
        self.next_row += 1

        # Create update indicator
        update_indicator = ctk.CTkLabel(self.jobs_frame, text="!", text_color="orange", width=20, font=("Arial", 32, "bold"))
        update_indicator.grid(row=row, column=0, padx=(0, 5), pady=(10, 2), sticky="w")
        update_indicator.bind("<Button-1>", lambda e, j=job_id: self.clear_update_indicator(j))

        # Hide update indicator if job is not updated
        if not updated:
            update_indicator.grid_remove()

        # Create and place widgets for each job field
        # Company
        company_entry = ctk.CTkEntry(self.jobs_frame, width=150)
        company_entry.insert(0, company)
        company_entry.grid(row=row, column=0, padx=(25, 5), pady=(10, 2), sticky="ew")
        company_entry.bind("<FocusOut>", lambda e, j=job_id, w=company_entry: self.validate_and_update(j, "company", w.get(), w))

        # Position
        position_entry = ctk.CTkEntry(self.jobs_frame, width=150)
        position_entry.insert(0, position)
        position_entry.grid(row=row, column=1, padx=5, pady=(10, 2), sticky="ew")
        position_entry.bind("<FocusOut>", lambda e, j=job_id, w=position_entry: self.validate_and_update(j, "position", w.get(), w))

        # Status
        status_var = ctk.StringVar(value=status)
        status_dropdown = ctk.CTkOptionMenu(self.jobs_frame, variable=status_var, values=["Applied", "Interview", "Offer", "Rejected"], width=100)
        status_dropdown.grid(row=row, column=2, padx=5, pady=(10, 2), sticky="ew")
        status_dropdown.configure(command=lambda v, j=job_id: self.update_job(j, "status", v))

        # Application Date
        app_date_entry = ctk.CTkEntry(self.jobs_frame, width=100)
        app_date_entry.insert(0, app_date)
        app_date_entry.grid(row=row, column=3, padx=5, pady=(10, 2), sticky="ew")
        app_date_entry.bind("<FocusOut>", lambda e, j=job_id, w=app_date_entry: self.validate_and_update(j, "application_date", w.get(), w))

        # Last Updated
        last_updated_label = ctk.CTkLabel(self.jobs_frame, text=last_updated, width=100)
        last_updated_label.grid(row=row, column=4, padx=5, pady=(10, 2), sticky="ew")

        # Notes
        notes_button = ctk.CTkButton(self.jobs_frame, text="Notes", width=50, command=lambda j=job_id, n=notes: self.open_notes(j, n))
        notes_button.grid(row=row, column=5, padx=5, pady=(10, 2))
        
        # Delete Button
        delete_button = ctk.CTkButton(self.jobs_frame, text="✕", width=30, height=30,fg_color="red", hover_color="dark red", command=lambda j=job_id: self.delete_job(j))
        delete_button.grid(row=row, column=6, padx=(5, 10), pady=(10, 2))

        # Store references to row widgets
        self.job_rows[job_id] = {"row": row, "update_indicator": update_indicator, "company": company_entry, "position": position_entry, "status": status_dropdown, 
                                "application_date": app_date_entry, "last_updated": last_updated_label, "notes": notes_button, "delete": delete_button}

    def update_job_row(self, job_id, field, value):
        """Update a specific field in a job row on the home screen."""
        if job_id in self.job_rows:
            if field == "last_updated":
                self.job_rows[job_id]["last_updated"].configure(text=value)
            elif field in ["company", "position", "application_date"]:
                if field in self.job_rows[job_id]:
                    self.job_rows[job_id][field].delete(0, ctk.END)
                    self.job_rows[job_id][field].insert(0, value)
                else:
                    logging.warning(f"Field '{field}' not found in job_rows for job_id {job_id}")
            elif field == "status":
                self.job_rows[job_id]["status"].set(value)
            elif field == "notes":
                # We don't need to update the UI for notes, as it's handled in a separate window
                pass
            elif field == "updated":
                if value:
                    self.job_rows[job_id]["update_indicator"].grid()
                else:
                    self.job_rows[job_id]["update_indicator"].grid_remove()
            else:
                logging.warning(f"Warning: Unhandled field '{field}' in update_job_row")

        logging.info(f"Updated job ID {job_id} field {field} to {value}")

    def clear_update_indicator(self, job_id):
        """Clear the update indicator for a job."""
        conn = sqlite3.connect("job_applications.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE jobs SET updated = 0 WHERE id = ?", (job_id,))
        conn.commit()
        conn.close()
        self.update_job_row(job_id, "updated", False)

    def remove_job_row(self, job_id):
        """Remove a job row from the UI and adjust remaining rows."""
        if job_id in self.job_rows:
            row = self.job_rows[job_id]["row"]

            # Destroy all widgets in the row
            for widget in self.job_rows[job_id].values():
                if isinstance(
                    widget,
                    (ctk.CTkEntry, ctk.CTkLabel, ctk.CTkButton, ctk.CTkOptionMenu),
                ):
                    widget.destroy()

            # Remove the job from our tracking dictionary
            del self.job_rows[job_id]

            # Shift remaining rows up
            for other_job_id, job_data in self.job_rows.items():
                if job_data["row"] > row:
                    job_data["row"] -= 1
                    for widget in job_data.values():
                        if isinstance(widget, (ctk.CTkEntry, ctk.CTkLabel, ctk.CTkButton, ctk.CTkOptionMenu,)):
                            widget.grid(row=job_data["row"])

            # Update the next available row
            self.next_row -= 1
        else:
            logging.warning(f"Attempted to remove non-existent job with ID {job_id}")

    def open_email_config(self):
        """Open the email configuration dialog."""
        EmailConfigDialog(self, self.config)

if __name__ == "__main__":
    app = HomeScreen()
    app.mainloop()
