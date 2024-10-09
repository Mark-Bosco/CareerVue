import customtkinter as ctk

class ContentWindow(ctk.CTkToplevel):
    """A window for displaying and editing job content."""

    def __init__(self, parent, job_id, content):
        """Initialize the content window."""
        super().__init__(parent)
        self.title("Job Content")
        self.geometry("1200x800")
        self.parent = parent
        self.job_id = job_id

        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.attributes('-topmost', True)  # Ensure window stays on top

        # Create UI elements
        self.create_widgets(content)

        # Set up window close protocol
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self, content):
        """Create and place widgets for the content window."""
        # Create main frame
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        # Create and place label for instructions
        instructions = ctk.CTkLabel(main_frame, text="Email Content", font=("Arial", 16, "bold"))
        instructions.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        # Create and place text box for content
        self.content_text = ctk.CTkTextbox(main_frame, height=300, font=("Arial", 12))
        self.content_text.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.content_text.insert(ctk.END, content)

        # Create and place save button
        self.save_button = ctk.CTkButton(main_frame, text="Save", command=self.save_content)
        self.save_button.grid(row=2, column=0, padx=10, pady=(0, 10))

    def save_content(self):
        """Save the updated content and close the window."""
        new_content = self.content_text.get("1.0", ctk.END).strip()
        self.parent.update_job(self.job_id, "content", new_content)
        self.on_closing()

    def on_closing(self):
        """Handle the window closing event."""
        self.destroy()