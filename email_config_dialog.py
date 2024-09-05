import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
import json

class EmailConfigDialog(ctk.CTkToplevel):
    """A dialog window for configuring email settings."""

    def __init__(self, parent, config=None):
        # Initialize the dialog window
        super().__init__(parent)
        self.parent = parent
        self.title("Email Configuration")
        self.geometry("400x250")
        self.attributes('-topmost', True)
        self.config = config or {}

        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Create and place widgets
        self._create_widgets()
            
        # Load existing configuration
        self.email_entry.insert(0, config.get("email", ""))
        self.password_entry.insert(0, config.get("password", ""))
        self.inbox_entry.insert(0, config.get("inbox", ""))
        self.server_entry.insert(0, config.get("imap_server", ""))

        # Set up window close protocol
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_widgets(self):
        """Create and place all widgets in the dialog."""
        # Email Address
        ctk.CTkLabel(self, text="Email Address:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.email_entry = ctk.CTkEntry(self)
        self.email_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Password
        ctk.CTkLabel(self, text="Password:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.password_entry = ctk.CTkEntry(self, show="*")
        self.password_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        
        # Inbox
        ctk.CTkLabel(self, text="Inbox:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        self.inbox_entry = ctk.CTkEntry(self)
        self.inbox_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

        # IMAP Server
        ctk.CTkLabel(self, text="IMAP Server:").grid(row=3, column=0, padx=10, pady=10, sticky="e")
        self.server_entry = ctk.CTkEntry(self)
        self.server_entry.grid(row=3, column=1, padx=10, pady=10, sticky="ew")

        # Save Button
        self.save_button = ctk.CTkButton(self, text="Save", command=self.save_config)
        self.save_button.grid(row=4, column=0, columnspan=2, padx=10, pady=20)

    def save_config(self):
        """Save the email configuration."""
        email = self.email_entry.get()
        password = self.password_entry.get()
        inbox = self.inbox_entry.get()
        server = self.server_entry.get()

        if email and password and inbox and server:
            new_config = {
                "email": email,
                "password": password,
                "inbox": inbox,
                "imap_server": server
            }
            with open("email_config.json", "w") as f:
                json.dump(new_config, f)
            
            # Update the parent's configuration and restart the email watcher
            self.parent.update_config(new_config)
            
            self.on_closing()
        else:
            CTkMessagebox(title="Error", message="Please fill in all fields.", icon="cancel")

    def on_closing(self):
        """Handle window closing event."""
        self.grab_release()
        self.destroy()