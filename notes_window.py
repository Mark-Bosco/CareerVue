import customtkinter as ctk

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

        # Create UI elements
        self.create_widgets(notes)

        # Set up window close protocol
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self, notes):
        """Create and place widgets for the notes window."""
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
        self.on_closing()

    def on_closing(self):
        """Handle the window closing event."""
        self.destroy()