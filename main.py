import time
import customtkinter as ctk
import sqlite3
from CTkMessagebox import CTkMessagebox
from datetime import datetime
import re
from email_watcher import EmailWatcher
import threading
import json
import os

class NotesWindow(ctk.CTkToplevel):
    """A window for displaying and editing job notes."""

    def __init__(self, parent, job_id, notes):
        super().__init__(parent)
        self.title("Job Notes")
        self.geometry("400x300")
        self.parent = parent
        self.job_id = job_id

        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.attributes('-topmost', True)  # Ensure window stays on top

        # Create and place text box for notes
        self.notes_entry = ctk.CTkTextbox(self, height=200)
        self.notes_entry.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.notes_entry.insert(ctk.END, notes)

        # Create and place save button
        self.save_button = ctk.CTkButton(self, text="Save", command=self.save_notes)
        self.save_button.grid(row=1, column=0, padx=10, pady=10)

    def save_notes(self):
        """Save the updated notes and close the window."""
        new_notes = self.notes_entry.get("1.0", ctk.END).strip()
        self.parent.update_job(self.job_id, "notes", new_notes)
        self.destroy()

class EmailConfigDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Email Configuration")
        self.geometry("400x250")
        self.attributes('-topmost', True)

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Email Address:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.email_entry = ctk.CTkEntry(self)
        self.email_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(self, text="Password:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.password_entry = ctk.CTkEntry(self, show="*")
        self.password_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(self, text="IMAP Server:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        self.server_entry = ctk.CTkEntry(self)
        self.server_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

        self.save_button = ctk.CTkButton(self, text="Save", command=self.save_config)
        self.save_button.grid(row=3, column=0, columnspan=2, padx=10, pady=20)

        self.load_config()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_config(self):
        if os.path.exists("email_config.json"):
            with open("email_config.json", "r") as f:
                config = json.load(f)
                self.email_entry.insert(0, config.get("email", ""))
                self.server_entry.insert(0, config.get("imap_server", ""))

    def save_config(self):
        email = self.email_entry.get()
        password = self.password_entry.get()
        server = self.server_entry.get()

        if email and password and server:
            config = {
                "email": email,
                "password": password,
                "imap_server": server
            }
            with open("email_config.json", "w") as f:
                json.dump(config, f)
            self.parent.after(100, self.parent.start_email_watcher)  # Defer the start of email watcher
            self.on_closing()
        else:
            CTkMessagebox(title="Error", message="Please fill in all fields.", icon="cancel")

    def on_closing(self):
        self.grab_release()
        self.destroy()

class HomeScreen(ctk.CTk):
    """The main application window for the job tracker."""

    def __init__(self):
        super().__init__()

        self.title("CareerVue - Job Application Tracker")
        self.geometry("1200x600")

        # Configure main grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.setup_top_frame()
        self.setup_main_frame()
        self.setup_jobs_frame()

        self.job_rows = {}  # Store references to job rows
        self.next_row = 1  # Start job rows from row 1 (after headers)

        self.email_watcher = None
        self.email_watcher_thread = None

        # Add email configuration button
        self.email_config_button = ctk.CTkButton(self.top_frame, text="Email Config", command=self.open_email_config)
        self.email_config_button.grid(row=0, column=1, padx=10, pady=10)

        self.refresh_jobs()

    def setup_top_frame(self):
        """Set up the top frame with logo, add button, and refresh button."""
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        self.top_frame.grid_columnconfigure(1, weight=1)

        self.logo_label = ctk.CTkLabel(self.top_frame, text="CareerVue", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self.email_config_button = ctk.CTkButton(self.top_frame, text="Email Config", command=self.open_email_config)
        self.email_config_button.grid(row=0, column=1, padx=10, pady=10)

        self.refresh_button = ctk.CTkButton(self.top_frame, text="🔄", width=40, font=("Arial", 20), command=self.refresh_emails_and_jobs)
        self.refresh_button.grid(row=0, column=2, padx=10, pady=10, sticky="e")

        self.add_job_button = ctk.CTkButton(self.top_frame, text="+", width=40, font=("Arial", 20), command=self.add_new_job)
        self.add_job_button.grid(row=0, column=3, padx=10, pady=10, sticky="e")

    def refresh_emails_and_jobs(self):
        """Refresh emails and update the job list."""
        if self.email_watcher:
            try:
                self.email_watcher.run()
                self.refresh_jobs()
                CTkMessagebox(title="Success", message="Emails checked and jobs refreshed!", icon="info")
            except Exception as e:
                print(f"Error refreshing emails: {e}")
                CTkMessagebox(title="Error", message="Failed to refresh emails. Please try again.", icon="cancel")
        else:
            CTkMessagebox(title="Error", message="Email watcher not configured. Please set up email configuration first.", icon="cancel")

    def start_email_watcher(self):
        if os.path.exists("email_config.json"):
            with open("email_config.json", "r") as f:
                config = json.load(f)
            
            self.email_watcher = EmailWatcher(config["email"], config["password"], config["imap_server"])
            
            # Test connection before starting the thread
            if self.email_watcher.connect():
                self.email_watcher_thread = threading.Thread(target=self.run_email_watcher, daemon=True)
                self.email_watcher_thread.start()
                CTkMessagebox(title="Success", message="Email watcher started successfully!", icon="info")
            else:
                CTkMessagebox(title="Error", message="Failed to connect to email server. Please check your credentials and try again.", icon="cancel")
        else:
            CTkMessagebox(title="Error", message="Email configuration not found.", icon="cancel")

    def run_email_watcher(self):
        while True:
            try:
                self.email_watcher.run()
                # Sleep for 5 minutes before checking again
                time.sleep(300)
            except Exception as e:
                print(f"Error in email watcher: {e}")
                # Sleep for 1 minute before retrying
                time.sleep(60)

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
        self.jobs_frame.grid_columnconfigure((5, 6), weight=0)  # Notes and Delete columns

        # Add headers with larger font
        headers = ["Company", "Position", "Status", "Application Date", "Last Updated", "", ""]
        for i, header in enumerate(headers):
            label = ctk.CTkLabel(self.jobs_frame, text=header, font=ctk.CTkFont(size=16, weight="bold"))
            label.grid(row=0, column=i, padx=5, pady=(5, 10), sticky="ew")
            if i < 5:  # Center text for all columns except Notes and Delete
                label.configure(anchor="center")

    def add_new_job(self):
        """Add a new job entry to the database and UI."""
        conn = sqlite3.connect("job_applications.db")
        cursor = conn.cursor()
        current_date = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            INSERT INTO jobs (company, position, status, application_date, last_updated, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("New Company", "New Position", "Applied", current_date, current_date, ""))
        job_id = cursor.lastrowid
        conn.commit()
        conn.close()
        self.add_job_row(job_id, "New Company", "New Position", "Applied", current_date, current_date, "")

    def delete_job(self, job_id):
        """Delete a job entry from the database and UI."""
        confirm = CTkMessagebox(title="Confirm Deletion", message="Are you sure you want to delete this job?", icon="question", option_1="Yes", option_2="No")
        if confirm.get() == "Yes":
            conn = sqlite3.connect("job_applications.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM jobs WHERE id=?", (job_id,))
            conn.commit()
            conn.close()
            self.remove_job_row(job_id)

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
            cursor.execute(f"UPDATE jobs SET {field} = ?, last_updated = ? WHERE id = ?", 
                           (value, current_date, job_id))
            conn.commit()
            self.update_job_row(job_id, field, value)
            if field != "notes":
                self.update_job_row(job_id, "last_updated", current_date)
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
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

        for job in jobs:
            job_id, company, position, status, app_date, last_updated, notes = job
            if job_id not in self.job_rows:
                self.add_job_row(job_id, company, position, status, app_date, last_updated, notes)
            else:
                self.update_job_row(job_id, "company", company)
                self.update_job_row(job_id, "position", position)
                self.update_job_row(job_id, "status", status)
                self.update_job_row(job_id, "application_date", app_date)
                self.update_job_row(job_id, "last_updated", last_updated)

    def add_job_row(self, job_id, company, position, status, app_date, last_updated, notes):
        """Add a new job row to the UI."""
        row = self.next_row
        self.next_row += 1

        # Create and place widgets for each job field
        company_entry = ctk.CTkEntry(self.jobs_frame, width=150)
        company_entry.insert(0, company)
        company_entry.grid(row=row, column=0, padx=5, pady=(10, 2), sticky="ew")
        company_entry.bind("<FocusOut>", lambda e, j=job_id, w=company_entry: self.validate_and_update(j, "company", w.get(), w))

        position_entry = ctk.CTkEntry(self.jobs_frame, width=150)
        position_entry.insert(0, position)
        position_entry.grid(row=row, column=1, padx=5, pady=(10, 2), sticky="ew")
        position_entry.bind("<FocusOut>", lambda e, j=job_id, w=position_entry: self.validate_and_update(j, "position", w.get(), w))

        status_var = ctk.StringVar(value=status)
        status_dropdown = ctk.CTkOptionMenu(self.jobs_frame, variable=status_var, values=["Applied", "Interview", "Offer", "Rejected"], width=100)
        status_dropdown.grid(row=row, column=2, padx=5, pady=(10, 2), sticky="ew")
        status_dropdown.configure(command=lambda v, j=job_id: self.update_job(j, "status", v))

        app_date_entry = ctk.CTkEntry(self.jobs_frame, width=100)
        app_date_entry.insert(0, app_date)
        app_date_entry.grid(row=row, column=3, padx=5, pady=(10, 2), sticky="ew")
        app_date_entry.bind("<FocusOut>", lambda e, j=job_id, w=app_date_entry: self.validate_and_update(j, "application_date", w.get(), w))

        last_updated_label = ctk.CTkLabel(self.jobs_frame, text=last_updated, width=100)
        last_updated_label.grid(row=row, column=4, padx=5, pady=(10, 2), sticky="ew")

        notes_button = ctk.CTkButton(self.jobs_frame, text="Notes", width=50, 
                                     command=lambda j=job_id, n=notes: self.open_notes(j, n))
        notes_button.grid(row=row, column=5, padx=5, pady=(10, 2))

        delete_button = ctk.CTkButton(self.jobs_frame, text="✕", width=30, height=30, 
                                      fg_color="red", hover_color="dark red",
                                      command=lambda j=job_id: self.delete_job(j))
        delete_button.grid(row=row, column=6, padx=(5, 10), pady=(10, 2))

        # Store references to row widgets
        self.job_rows[job_id] = {
            "row": row,
            "company": company_entry,
            "position": position_entry,
            "status": status_dropdown,
            "application_date": app_date_entry,
            "last_updated": last_updated_label,
            "notes": notes_button,
            "delete": delete_button
        }

    def update_job_row(self, job_id, field, value):
        """Update a specific field in a job row."""
        if job_id in self.job_rows:
            if field == "last_updated":
                self.job_rows[job_id]["last_updated"].configure(text=value)
            elif field in ["company", "position", "application_date"]:
                if field in self.job_rows[job_id]:
                    self.job_rows[job_id][field].delete(0, ctk.END)
                    self.job_rows[job_id][field].insert(0, value)
                else:
                    print(f"Warning: Field '{field}' not found in job_rows for job_id {job_id}")
            elif field == "status":
                self.job_rows[job_id]["status"].set(value)
            elif field == "notes":
                # We don't need to update the UI for notes, as it's handled in a separate window
                pass
            else:
                print(f"Warning: Unhandled field '{field}' in update_job_row")

    def remove_job_row(self, job_id):
        """Remove a job row from the UI and adjust remaining rows."""
        if job_id in self.job_rows:
            row = self.job_rows[job_id]["row"]
            for widget in self.job_rows[job_id].values():
                if isinstance(widget, (ctk.CTkEntry, ctk.CTkLabel, ctk.CTkButton, ctk.CTkOptionMenu)):
                    widget.destroy()
            del self.job_rows[job_id]
            
            # Shift remaining rows up
            for other_job_id, job_data in self.job_rows.items():
                if job_data["row"] > row:
                    job_data["row"] -= 1
                    for widget in job_data.values():
                        if isinstance(widget, (ctk.CTkEntry, ctk.CTkLabel, ctk.CTkButton, ctk.CTkOptionMenu)):
                            widget.grid(row=job_data["row"])
            
            self.next_row -= 1

    def open_email_config(self):
        EmailConfigDialog(self)

    def start_email_watcher(self):
        if os.path.exists("email_config.json"):
            with open("email_config.json", "r") as f:
                config = json.load(f)
            
            self.email_watcher = EmailWatcher(config["email"], config["password"], config["imap_server"])
            self.email_watcher_thread = threading.Thread(target=self.run_email_watcher, daemon=True)
            self.email_watcher_thread.start()
            
            CTkMessagebox(title="Success", message="Email watcher started successfully!", icon="info")
        else:
            CTkMessagebox(title="Error", message="Email configuration not found.", icon="cancel")

if __name__ == "__main__":
    app = HomeScreen()
    app.mainloop()