# Ebook Manager

A Flask-based web application for managing ebooks.

## Features
- User authentication
- Ebook upload, edit, delete
- Metadata management
- Logging system
- table schemas are creaed when you excute this initially.

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/ksyang00/ai_ebook_manger.git

2. This application was built using Python 3.11.9 and the database is PostgreSQL 16.7.
    Before running the code, please create the ebookdb database and then execute the application.
    The tables will be created automatically upon the first run.

3. Run
    "python app.py" or "flash run"

   
## folder structures
   
   ai_ebook_manager
   
   ├── README.md
   
   ├── app.py
   
   ├── config.py
   ├── events.py
   ├── models.py
   ├── requirements.txt
   ├── routes.py
   ├── static
   │   ├── scripts.js
   │   └── styles.css
   ├── templates
   │   ├── delete_ebook.html
   │   ├── delete_user.html
   │   ├── detail.html
   │   ├── ebook_all.html
   │   ├── edit_ebook.html
   │   ├── edit_user.html
   │   ├── layout.html
   │   ├── list.html
   │   ├── login.html
   │   ├── logs.html
   │   ├── manage_users.html
   │   ├── register.html
   │   └── upload.html
   └── utils.py

