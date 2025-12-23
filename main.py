import requests
from bs4 import BeautifulSoup
import json
import sys
import time
import ollama

from ebay import (
    search_ebay_items,
    generate_ebay_auth_url,
    exchange_ebay_code_for_token
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
SEEN_IDS = set()

def check_new_posts(search_url) -> list[str]:
    response = requests.get(search_url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(response.text, 'html.parser')

    new_posts: list[str] = []
    urls: list[str] = []

    for h3 in soup.find_all('h3'):
        a = h3.find('a', attrs={'data-testid': 'rich-card-link'}, href=True)
        if a:
            urls.append(a['href'])    

    for href in urls:
        post_id = href.split('/')[-1]

        if post_id and post_id not in SEEN_IDS:
            SEEN_IDS.add(post_id)
            new_posts.append(href)

    return new_posts

def scrape_kijiji_ad(url: str) -> dict:
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract title
        title_elem = soup.find('h1')
        title = title_elem.text.strip() if title_elem else 'N/A'

        # Extract price
        price_elem = soup.find('p', {'data-testid': 'vip-price'})
        price = price_elem.text.strip() if price_elem else 'N/A'

        # Extract description
        desc_elem = soup.find('div', {'data-testid': 'vip-description-wrapper'})
        description = desc_elem.get_text(separator='\n').strip() if desc_elem else 'N/A'

        # Extract location
        location = 'N/A'
        ld_json = soup.find('script', type='application/ld+json')

        if ld_json:
            try:
                data = json.loads(ld_json.string)

                location = (
                    data.get('offers', {})
                        .get('availableAtOrFrom', {})
                        .get('address', {})
                        .get('streetAddress', 'N/A')
                )
            except (json.JSONDecodeError, TypeError):
                pass

        # Fallback to old DOM-based approach if JSON-LD fails
        if location == 'N/A':
            loc_elem = (
                soup.find('span', class_='location-1732119168') or
                soup.find('span', class_='address-3617944557')
            )
            location = loc_elem.text.strip() if loc_elem else 'N/A'

        # Return as dict
        data = {
            'title': title,
            'price': price,
            'description': description,
            'location': location,
            'url': url
        }
        return data

    except Exception as e:
        return {'error': str(e)}

def evaluate_deal(ad_data: dict) -> str:
    prompt = f"""
    You are an expert in evaluating online classified ads for computer components. Based on the following ad details, determine how good of a deal the price represents compared to the market value for similar items.

    Ad Details:
    Title: {ad_data['title']}
    Price: {ad_data['price']}
    Description: {ad_data['description']}
    Location: {ad_data['location']}
    URL: {ad_data['url']}

    Provide the deal evaluation score on a scale of 1 to 100, where 100 means an excellent deal and 1 means a terrible deal. Use the following guideline to evaluate the score:
    
    - At market value: 40
    - 10% below market value: 50
    - 20% below market value: 60
    - 30% below market value: 70
    - 40% below market value: 80
    - 50% below market value: 90    
    
    Only consider the price in your evaluation and compare it to what the market price is for the item based on the title and description. Do not assume that any listing is a scam or has any hidden issues. If you determine that the listing is for a bundle (multiple items), evaluate the score as 50 and output that it is a bundle. If the score falls between the defined thresholds, estimate accordingly.
    
    Please return your response strictly in the following JSON format:
    {{
        "deal_score": <1-100>,
        "reasoning": <string explaining the score>
        "is_bundle": <true/false>
    }}
    """
    client = ollama.Client()
    model = "deepseek-r1:8b"

    response = client.generate(model=model, prompt=prompt)

    return response.response

if __name__ == '__main__':
    print(exchange_ebay_code_for_token("","","",""))
    # with open("test.txt", "w", encoding="utf-8") as file:
    #     file.write(json.dumps(search_ebay_items(), indent=4) + "\n\n")
   
    # while True:
    #     print("Checking for new listings...")
    #     new_ads = check_new_posts(
    #         "https://www.kijiji.ca/b-computer-components/city-of-toronto/c788l1700273"
    #     )
    #     for ad in new_ads[1:]:
    #         listing = scrape_kijiji_ad(ad)
    #         print("New listing found:", listing)
    #         evaluation = evaluate_deal(listing)
            
    #         with open("output.txt", "a", encoding="utf-8") as file:
    #             file.write(json.dumps(listing, indent=4) + "\n\n")
    #             file.write(evaluation)
    #             file.write("\n\n")

    #     time.sleep(300)  # every 5 minutes