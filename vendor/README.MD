
Deployment README

Project Name
1929 Way

Deployment Instructions

Prerequisites
1. Python Version:Python 3.10.5
2.Django Version: Django 5.0.4
3. Database: PostgreSQL

Environment Setup
1. Clone the Repository      Bash

    git clone [repository-url]
    cd [repository-directory]


2.Create and Activate a Virtual Environment      
    Bash
    python -m venv venv
    source venv/bin/activate
    # On Windows, use `venv\Scripts\activate`


3. Install Dependencies
    Bash
    pip install -r requirements.txt

Configuration

1.Database Configuration
    - Update the `DATABASES` settings in `settings.py` with your database credentials.

2.Environment Variables
    - Set up environment variables required by the application From .env file in main project directory(Bookingapp_1969). These might include:
        - DJANGO_SECRET_KEY
        - DEBUG
        - ALLOWED_HOST
        - DATABASE_URL
        - EMAIL_HOST   
        - EMAIL_PORT
        - EMAIL_HOST_USER   
        - EMAIL_HOST_PASSWORD

3. Static and Media Files
    - Ensure paths for static and media files are configured correctly in `settings.py`.
    - Collect static files:
        Bash
        python manage.py collectstatic
  

Database Setup

1. Apply Migrations
    Bash
   python manage.py makemigrations
   python manage.py migrate

2.Create Superuser (Optional)
    Bash
    python manage.py createsuperuser


Running the Application

1.Run the Development Server
   Bash
    python manage.py runserver


Testing
1.Run Tests 
    Bash
    python manage.py test

