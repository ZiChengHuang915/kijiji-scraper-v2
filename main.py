import os
import requests
from bs4 import BeautifulSoup
import json
import sys
import time
import ollama
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

KIJIJI_POST_URL = "https://www.kijiji.ca/b-computer-components/city-of-toronto/c788l1700273"

load_dotenv()

from ebay import (
    search_ebay_items,
    get_ebay_token,
    exchange_ebay_code_for_token,
    get_average_ebay_price,
    get_average_ebay_price_with_trimming,
    get_condensed_ebay_listings,
)

from kijiji import (
    check_new_posts,
    scrape_kijiji_ad, 
)

import database

# TODOs
# make bundle detection looser, only check if multiple prices are listed
# if "price": "Free", score should be 100 
# error checkng if AI output is not a json
# email notification if good deal
# query ebay for average price based on title
# algorithmic calculation of score based on market discount
# dump all ids to a database, maybe excel
# handle bundle deals, maybe query ebay multiple times or use the most expensive item (or first item)

def cleanup_title_string(title: str) -> str:
    client = ollama.Client()
    prompt = f"""
    You are a helpful assistant that extracts the main product name from a given title string for computer components. Remove any unnecessary details such as specifications, conditions, or seller notes, and return a concise product name. Make sure to autocorrect any spelling mistakes.
    
    Keep any technical details that are part of the product name itself, such as the amount of storage (e.g., "1 TB") or memory size (e.g., "16 GB").

    For computer memory (RAM) products, ensure to include the type (e.g., DDR4, DDR3), speed (e.g., 3200MHz), and form factor (e.g., DIMM, SO-DIMM) in the product name. Do not include the speed or channel (e.g. 8GB x 2).

    For power supply units (PSUs) and storage drives, only include the wattage or storage capacity. Do not include the specific brand name or model number.

    For liquid coolers, only include the radiator size (e.g., 240mm, 360mm). Do not include the brand name or model number.

    Examples:
    - Input: "RTX 4500 AD102 24GB GDDR6"
      Output: "RTX 4500"
    - Input: "Crucial X10 6TB Portable SSD(CT6000X10SSD9)"
      Output: "6TB Portable SSD"
    - Input: "ASUS ROG RYUJIN III 360 ARGB EXTREME - AIO (WHITE)"
      Output: "360mm AIO Liquid Cooler"

    The title string is "{title}". Return only the cleaned product name without any additional text."""
    model = "deepseek-r1:8b"

    response = client.generate(model=model, prompt=prompt)
    return response.response

def filter_component_listing(listing: dict) -> bool:
    client = ollama.Client()
    prompt = f"""
    You are a helpful assistant that determines whether a given classified ad listing is for a computer component or not.
    
    The listing details are as follows:
    Title: {listing['title']}
    Description: {listing['description']}

    Filter out any components that are older than 2015. Filter out any computer memory that is DDR3 or older. Filter out any laptop components. Filter out any non-computer components. Filter out any accessories (cables, adapters, peripherals, etc.). Filter out any add-on or adapter cards.

    Only keep the following computer components:
    - CPUs
    - CPU Coolers
    - GPUs
    - RAM (DDR4 or newer)
    - Motherboards
    - Storage drives (HDDs, SSDs)
    - Power supply units (PSUs)
    - Cases
    
    Return only the string "True" if it passes the filter, or "False" if it does not.
    """
    model = "deepseek-r1:8b"

    response = client.generate(model=model, prompt=prompt)
    return response.response == "True"

def evaluate_deal(listing: dict) -> dict:
    should_keep = filter_component_listing(listing)
    ad_price = listing['price']
    if ad_price == -1:
        should_keep = False

    deal = {
        "listing": listing,
        "should_keep": should_keep,
        "percentile_score": 100.0,
        "ebay search title": "N/A",
        "average_ebay_price": 0.0,
        "ebay_listings": {"item": []},
    }

    if not should_keep:
        return deal
    
    title = cleanup_title_string(listing['title'])
    
    condensed_listings = get_condensed_ebay_listings(title)
    average_ebay_price = get_average_ebay_price_with_trimming(condensed_listings)
    
    percentile_score = ad_price / average_ebay_price * 100 if average_ebay_price > 0 else 100.0
    
    deal["percentile_score"] = percentile_score
    deal["ebay search title"] = title
    deal["average_ebay_price"] = average_ebay_price
    deal["ebay_listings"] = {"item": condensed_listings}
    return deal

def send_evaluation_email(evaluation: dict, recipient_email: str):
    """Send an email containing the evaluation JSON to the specified recipient"""
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', 587))
    sender_email = os.getenv('SENDER_EMAIL')
    sender_password = os.getenv('SENDER_PASSWORD')
    
    if not all([sender_email, sender_password]):
        print("Email configuration not found in environment variables")
        return False
    
    # Create message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = f"Kijiji Scraper v2: {evaluation['listing']['title']}"

    
    # Format the JSON nicely
    json_body = json.dumps(evaluation, indent=2)
    
    # Create email body
    body = f"""
Deal: {evaluation['listing']['title']}
Price: ${evaluation['listing']['price']}
Link: {evaluation['listing']['url']}

Full Evaluation JSON:
{json_body}
"""
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        # Create SMTP session
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        
        # Send email
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        
        print(f"Email sent successfully to {recipient_email}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

if __name__ == '__main__':
    conn = database.create_connection("deals.db")
    database.create_table(conn)

    with open("output.txt", "w", encoding="utf-8") as file:
        file.write("----- New Run -----\n\n")

    while True:
        new_ads_urls = check_new_posts(KIJIJI_POST_URL)
        for ad_url in new_ads_urls:
            listing = scrape_kijiji_ad(ad_url)
            
            if not database.evaluation_exists(conn, listing):
                evaluation = evaluate_deal(listing)
                print("inserting new evaluation for listing:", listing['title'])
                database.insert_evaluation(conn, evaluation)

                print("sending email for listing:", listing['title'])
                send_evaluation_email(evaluation, "zichuang127@gmail.com")

                with open("output.txt", "a", encoding="utf-8") as file:
                    file.write(json.dumps(evaluation, indent=4))
                    file.write("\n\n")
            else:
                print("evaluation already exists for listing:", listing['title'])

        time.sleep(300)  # every 5 minutes