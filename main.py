import os
import requests
from bs4 import BeautifulSoup
import json
import sys
import time
import ollama
from dotenv import load_dotenv

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

def evaluate_deal(listing: dict) -> str:
    should_keep = filter_component_listing(listing)
    if not should_keep:
        return json.dumps({
            "listing": listing,
            "should_keep": should_keep,
            "deal_score": 100.0,
            "ebay search title": "N/A",
            "average_ebay_price": 0.0,
            "ebay_listings": {"item": []},
        }, indent=4)
    
    title = cleanup_title_string(listing['title'])
    ad_price = listing['price']
    condensed_listings = get_condensed_ebay_listings(title)
    average_ebay_price = get_average_ebay_price_with_trimming(condensed_listings)
    
    deal_score = ad_price / average_ebay_price * 100 if average_ebay_price > 0 else 100.0
    return json.dumps({
        "listing": listing,
        "should_keep": should_keep,
        "deal_score": deal_score,
        "ebay search title": title,
        "average_ebay_price": average_ebay_price,
        "ebay_listings": {"item": condensed_listings},
    }, indent=4)

if __name__ == '__main__':
    if False:
        # with open("test.txt", "w", encoding="utf-8") as file:
        #     file.write(json.dumps(get_condensed_ebay_listings("Computer RAM: Kingston ValueRAM 1 GB 400MHz DDR DIMM"), indent=4) + "\n\n")

        with open("output.txt", "w", encoding="utf-8") as file:
            file.write("----- New Run -----\n\n")
    
        while True:
            print("Checking for new listings...")
            new_ads_urls = check_new_posts(KIJIJI_POST_URL)
            for ad_url in new_ads_urls:
                listing = scrape_kijiji_ad(ad_url)
                print("New listing found:", listing)
                evaluation = cleanup_title_string(listing['title'])
                
                with open("output.txt", "a", encoding="utf-8") as file:
                    file.write(json.dumps(listing, indent=4) + "\n\n")
                    file.write(evaluation)
                    file.write("\n\n")

            time.sleep(300)  # every 5 minutes
    else:
        with open("output.txt", "w", encoding="utf-8") as file:
            file.write("----- New Run -----\n\n")
    
        while True:
            new_ads_urls = check_new_posts(KIJIJI_POST_URL)
            for ad_url in new_ads_urls:
                listing = scrape_kijiji_ad(ad_url)
                evaluation = evaluate_deal(listing)
                
                with open("output.txt", "a", encoding="utf-8") as file:
                    file.write(evaluation)
                    file.write("\n\n")

            time.sleep(300)  # every 5 minutes