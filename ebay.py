import requests
import base64

def exchange_ebay_code_for_token(client_id, client_secret, scope):
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

def search_ebay_items(params, token=None):
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
    url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    params = {'q': 'rtx 3080', 'limit': '3', 'category_ids': '175673', "filter": "conditions:{USED}"}
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'

    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()  # Raise an exception for bad status codes
    return response.json()