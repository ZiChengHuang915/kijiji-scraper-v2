import numpy as np
import os
import requests
import base64
import time
from dotenv import set_key, find_dotenv, load_dotenv

SEARCH_LIMIT = 20
COMPUTER_COMPONENTS_CATEGORY_ID = 175673
FILTER_CONDITIONS = "conditions:{NEW|USED}"


def get_ebay_token() -> str:
    """
    Gets a valid eBay OAuth access token, refreshing it if necessary.

    Returns:
        str: eBay OAuth access token.
    """
    current_time = time.time()
    if current_time > float(os.getenv("EBAY_TOKEN_EXPIRY", 0)):
        print("Refreshing eBay token...")

        client_id = os.getenv("EBAY_CLIENT_ID")
        client_secret = os.getenv("EBAY_CLIENT_SECRET")
        api_scope = os.getenv("EBAY_API_SCOPE")
        response = exchange_ebay_code_for_token(client_id, client_secret, api_scope)

        dotenv_path = find_dotenv()
        set_key(dotenv_path, "EBAY_TOKEN", response['access_token'])
        set_key(dotenv_path, "EBAY_TOKEN_EXPIRY", str(current_time + response['expires_in']))
        load_dotenv()
        return response['access_token']
    else:
        print("eBay token is still valid, using existing token.")
        return os.getenv("EBAY_TOKEN")


def exchange_ebay_code_for_token(client_id, client_secret, scope) -> dict:
    """
    Exchange the authorization code for an access token.

    Args:
        client_id (str): Your eBay app's client ID.
        client_secret (str): Your eBay app's client secret.
        ru_name (str): Your registered redirect URI name.
        auth_code (str): The authorization code received from the redirect.

    Returns:
        dict: JSON response containing the access token and other details.
    """
    token_url = "https://api.ebay.com/identity/v1/oauth2/token"

    # Base64 encode client_id:client_secret
    credentials = f"{client_id}:{client_secret}"
    encoded_creds = base64.b64encode(credentials.encode()).decode()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded_creds}"
    }
    payload = {
        "grant_type": "client_credentials",
        "scope": scope,
    }

    response = requests.post(token_url, headers=headers, data=payload)
    response.raise_for_status()
    return response.json()

def search_ebay_items(query_string:str, token=None) -> dict:
    """
    Make a GET request to eBay's item summary search API.

    Args:
        params (dict): Dictionary of query parameters for the search.
                       Possible keys: q, gtin, charity_ids, fieldgroups,
                       compatibility_filter, auto_correct, category_ids,
                       filter, sort, limit, offset, aspect_filter, epid
        token (str, optional): OAuth token for authorization. If provided,
                               it will be included in the Authorization header.

    Returns:
        dict: JSON response from the API if successful, else raises an exception.
    """
    if not token: 
        token = get_ebay_token()

    url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    params = {
        'q': query_string,
        'auto_correct' : "KEYWORD",
        'limit': SEARCH_LIMIT,
        'category_ids': COMPUTER_COMPONENTS_CATEGORY_ID,
        "filter": FILTER_CONDITIONS
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_CA"
    }

    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()

def get_average_ebay_price(condensed_listings: list[dict]) -> float:
    if not condensed_listings:
        return 0.0

    total_price = sum(item['price'] for item in condensed_listings)
    average_price = total_price / len(condensed_listings)
    return average_price

def get_average_ebay_price_with_trimming(condensed_listings: list[dict]) -> float:
    if not condensed_listings:
        return 0.0

    prices = [item['price'] for item in condensed_listings]
    q3 = np.quantile(prices, 0.75)
    q1 = np.quantile(prices, 0.15) # make it looser

    # Keep values strictly less than the 75th percentile
    filtered_prices = [x for x in prices if x < q3 and x > q1]
    return sum(filtered_prices) / len(filtered_prices) if filtered_prices else 0.0

def get_condensed_ebay_listings(item_title: str) -> list[dict]:
    search_results = search_ebay_items(item_title)
    condensed_listings = []

    for item in search_results.get('itemSummaries', []):
        price = float(item.get('price', {}).get('value', 'N/A')) + float(item.get('shippingOptions', [{}])[0].get('shippingCost', {}).get('value', 0))

        listing = {
            'title': item.get('title', 'N/A'),
            'price': price,
            'condition': item.get('condition', 'N/A'),
            'url': item.get('itemWebUrl', 'N/A')
        }
        condensed_listings.append(listing)

    return condensed_listings