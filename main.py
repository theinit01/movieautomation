import os
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import re
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime

load_dotenv()

uri = os.getenv('MONGODB_URI')
bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

client = MongoClient(uri, server_api=ServerApi('1'))
db = client['movieautomation']
collection = db['titles']

# List of URLs and corresponding search terms
url_search_terms = {
    'https://ssrmovies.forum/category/bollywood-movies/': ['WEB-DL', 'Hindi'],
    'https://ssrmovies.forum/category/web-series/': ['WEB-DL', 'Hindi'],
    'https://ssrmovies.forum/category/punjabi-movies/': ['WEB-DL']
}

# Define headings for each URL
url_headings = {
    'https://ssrmovies.forum/category/bollywood-movies/': 'Hindi Movies',
    'https://ssrmovies.forum/category/web-series/': 'Web Series',
    'https://ssrmovies.forum/category/punjabi-movies/': 'Punjabi Movie Titles'
}

# Function to fetch existing titles from MongoDB
def fetch_existing_titles(collection):
    return set(doc['title'] for doc in collection.find({}, {'title': 1, '_id': 0}))

# Function to fetch and process titles from a URL
def process_url(url, existing_titles, collection, search_terms):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to retrieve the webpage: {url}")
        return []

    exclude_term = 'Ullu'
    soup = BeautifulSoup(response.text, 'html.parser')
    text = soup.get_text()

    # Split the text into lines
    lines = text.splitlines()

    # Use regex to find lines containing the search terms and exclude lines with exclude_term
    include_pattern = re.compile(rf'(?=.*{re.escape(search_terms[0])})(?=.*{re.escape(search_terms[1] if len(search_terms) > 1 else "")})', re.IGNORECASE)
    exclude_pattern = re.compile(re.escape(exclude_term), re.IGNORECASE)

    # Filter lines to include both terms and exclude unwanted term
    matching_lines = [
        line for line in lines
        if include_pattern.search(line) and not exclude_pattern.search(line)
    ]

    # Regex to capture year and optional season/episode info
    year_season_pattern = re.compile(r'(\d{4})(.*?)(S\d{2}(?:-E\d{2})?)?', re.IGNORECASE)

    # Trim each line up to the year and include season/episode indicators if present
    trimmed_lines = []
    for line in matching_lines:
        match = year_season_pattern.search(line)
        if match:
            year = match.group(1)
            season_info = match.group(2).strip() + (match.group(3) if match.group(3) else '')
            year_index = match.start(1) + 4
            trimmed_lines.append(line[:year_index] + season_info)

    # Check and return new titles that are not in the database
    new_titles = [line for line in trimmed_lines if line not in existing_titles]
    return new_titles

# Function to insert new titles into MongoDB
def insert_new_titles(titles, collection):
    for title in titles:
        document = {
            'title': title,
            'date_added': datetime.now()
        }
        collection.insert_one(document)

# Function to send message via Telegram
def send_telegram_message(bot_token, chat_id, message):
    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown'  # Enables Markdown formatting
    }
    telegram_response = requests.post(telegram_url, data=payload)
    if telegram_response.status_code != 200:
        print("Failed to send message via Telegram.")
    else:
        print("Message sent via Telegram.")

# Main logic
existing_titles = fetch_existing_titles(collection)

for url, search_terms in url_search_terms.items():
    new_titles = process_url(url, existing_titles, collection, search_terms)
    
    if new_titles:
        print(f"New titles from {url}:")
        for title in new_titles:
            print(title)
        
        # Insert new titles into MongoDB
        insert_new_titles(new_titles, collection)
        print(f"Inserted {len(new_titles)} new titles into the collection.")
        
        # Generate and send fancy message via Telegram
        heading = url_headings.get(url, 'New Titles')
        message = f"*{heading}:*\n" + "\n".join([f"• {title}" for title in new_titles])
        send_telegram_message(bot_token, chat_id, message)

    else:
        print(f"No new titles found for {url}.")