import requests
from bs4 import BeautifulSoup
import json
from dotenv import load_dotenv

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
    """
    Scrape a Kijiji ad given its url and extract relevant details.
    
    Returns:
        dict: A dictionary containing title, price, description, location, and url.
    """
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
        price = float(price.replace("$", "")) if price != 'N/A' else price

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