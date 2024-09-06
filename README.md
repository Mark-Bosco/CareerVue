# CareerVue: Your Intelligent Job Application Tracker

[![Python](https://img.shields.io/badge/Python-3.7%2B-blue)](https://www.python.org/downloads/)
[![CustomTkinter](https://img.shields.io/badge/CustomTkinter-5.1.2-orange)](https://github.com/TomSchimansky/CustomTkinter)
[![SQLite](https://img.shields.io/badge/SQLite-3-green)](https://www.sqlite.org/index.html)

CareerVue is a sophisticated, AI-powered job application tracking system designed to streamline your job search process. Built with Python and leveraging advanced NLP techniques, CareerVue offers a seamless experience for managing your job applications, from initial submission to final offer.

## 🌟 Key Features

### 🤖 Intelligent Email Integration
- Automatically scans and categorizes job-related emails
- Uses Natural Language Processing (NLP) to extract key information
- Supports major email providers through IMAP

### 📊 Intuitive User Interface
- Clean, modern design built with CustomTkinter
- Real-time status updates with color-coded indicators
- Easy-to-use job entry and editing system

### 🔍 Smart Job Management
- Automatically categorizes applications (Applied, Interview, Offer, Rejected)
- Intelligent parsing of job titles and company names
- Customizable notes section for each application

### 🔒 Secure and Private
- Local SQLite database for data storage
- Encrypted email credentials
- No cloud sync - your data stays on your machine

## 🛠 Technical Highlights

- **Modular Architecture**: Well-structured codebase with clear separation of concerns
- **Multithreading**: Efficient background email processing
- **Error Handling**: Robust error management with detailed logging
- **Database Management**: Efficient SQLite operations with proper connection handling
- **NLP Integration**: Advanced text processing using NLTK
- **UI Design**: Responsive and accessible interface using CustomTkinter

## 🚀 Getting Started

### Prerequisites
- Python 3.7 or higher
- pip (Python package installer)

### Installation
1. Clone the repository:
   ```
   git clone https://github.com/yourusername/careervue.git
   ```
2. Navigate to the project directory:
   ```
   cd careervue
   ```
3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

### How to Use CareerVue

1. **Launch the Application**
   - Run `python home_screen.py` from the command line in the project directory.

2. **Configure Email Integration**
   - On first launch, you'll be prompted to set up your email configuration.
   - Enter your email address, password, inbox name, and IMAP server details.

3. **Add Job Applications**
   - Click the "+" button to manually add a new job application.
   - Fill in the company name, position, application date, and status.

4. **Manage Applications**
   - View all your applications in the main window.
   - Click on any field to edit the information.
   - Use the status dropdown to update the application status.

5. **Add Notes**
   - Click the "Notes" button for any application to add or edit detailed notes.

6. **Automatic Email Scanning**
   - CareerVue will periodically scan your email for new job-related messages.
   - New applications or updates will be automatically added to your dashboard.

7. **Refresh and Sync**
   - Click the "Refresh" button to manually trigger an email check and update your dashboard.

8. **Customize Settings**
   - Adjust the auto-check interval in the preferences section at the bottom of the window.

## 🚨 Important Note

CareerVue is currently in early development and testing phase. While functional, it may contain bugs and is subject to frequent updates and changes.

---

Put your current job hunt in the rearview with CareerVue!
