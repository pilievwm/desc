import requests
import os
import json
import re
import openai
from datetime import datetime
import time
from bs4 import BeautifulSoup
from flask_socketio import SocketIO, emit
from config import Config
from sqlalchemy import func, desc
from urllib.parse import urlparse
import wikipedia
from dotenv import load_dotenv

load_dotenv()   # Load environment variables from .env file

API_KEY = os.getenv('google_search_api_key')
UNSPLASH_API_KEY = os.getenv('unsplash')
CSE_ID = os.getenv('cse_id')

### CHECK FOR VALID URL ###
def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


### GOOGLE TRANSLATE ###
def google_translate(text, language):
    # Replace with your Google Cloud Translation API key
    api_key = API_KEY
    
    url = f"https://translation.googleapis.com/language/translate/v2?key={api_key}"
    
    data = {
        'q': text,
        'target': language
    }
    
    response = requests.post(url, data=data)

    if response.status_code == 200:
        translation = response.json()['data']['translations'][0]['translatedText']
        return translation
    else:
        return {"error": f"Google Translate API request failed with status code {response.status_code}"}
    

### GET IMAGES FROM UNSPLASH ###
def get_unsplash_image(category_settings, query):

    """Get an image from Unsplash for a given query"""
    endpoint = "https://api.unsplash.com/search/photos"
    headers = {f"Authorization": UNSPLASH_API_KEY}
    params = {"query": query}
    response = requests.get(endpoint, headers=headers, params=params)
    print(response)
    image_urls = []
    if response.status_code == 200:
        data = response.json()
        for result in data['results']:
            if 'small' in result['urls']:
                if len(image_urls) < category_settings['number_images']:  
                    image_urls.append(result['urls']['small'])  # Getting 'small' urls
                else:
                    break  # If we already have enough urls, stop adding
        return ','.join(image_urls)  # Convert the list to a JSON string to return it
    else:
        return "Error: Unsplash API request failed."
    
# Function to perform a Google Custom Search
def google_custom_search(query):
    # You need to set up a Google Custom Search JSON API and get an API key and search engine ID
    # For the purpose of this example, we are assuming that you have them set as environment variables
    api_key = API_KEY
    cse_id = CSE_ID

    # The base url for the Google Custom Search JSON API
    base_url = "https://www.googleapis.com/customsearch/v1"

    # Define the search parameters
    search_params = {
        "key": api_key,
        "cx": cse_id,
        "q": query,
    }
    # Send a GET request to the Google Custom Search JSON API
    response = requests.get(base_url, params=search_params)

    # If the request was successful, return the search results
    if response.status_code == 200:
        response_data = response.json()
        first_result = response_data.get("items", [{}])[0]
        first_result_link = first_result.get('link', '')  # Get the 'link' from the first result
        return first_result_link  # Now the function returns the link as a string
    else:
        return {"error": f"Google Custom Search failed with status code {response.status_code}."}


### OPENAI FUNCTIONS ###
def openaisearch(db, Category_Settings, app_settings, google_related_searches, query):

    openai.api_key = app_settings['openai_key']

    # Modify the prompt to ask for keywords for the specific property value
    #prompt = (f"Clean the related searches {google_related_searches} from brands of online stores or websites except this that are related with {app_settings['url']}. Leave only the best and relevant searches to the main query: '{query}' and remove from the result other brands of online retailers. The website is {app_settings['url']} and this information is only fot your referese. For example if you have related searches: Bestbuy soundebars, Ebay soundebars, Cheap soundbars, in this case Bestbuy and Ebay are other brands of online retailers that should be removed and leave only Cheap soundbars.")
    prompt = (f"Use that related searches {google_related_searches} from the main query: '{query}' and remove brands and websites or second hand related keywords. Leave only the best and relevant searches that are relevant for an online store and make sure that there are no other brands of online retailers. The website is {app_settings['url']} and this information is only fot your referese. For example if you have related searches: Bestbuy soundebars, Ebay soundebars, Cheap soundbars, in this case Bestbuy and Ebay are other brands of online retailers that should be removed and leave only Cheap soundbars.")
    #prompt = (f"As an highly skilled SEO expert your task is to choose the best and most relevant keywords for your SEO strategy. This is a list of related searches at google serp: {google_related_searches} from the main query: '{query}'")
    #prompt = (f"As a Bulgarian SEO researcher, craft at least {category_settings['max_keywords']} SEO optimized keywords for the property '{property_name}' with value '{value}' in the category '{category_name}'. ***Do not include only the property value, but also additional related keywords.***")
    
    system_prompt = (
        '***IMPORTANT! Return only the result without anything other words. The result should be comma separated ***'
    )

    max_retries = 15
    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(
                model=app_settings['seo_model'],
                messages=[
                    {"role": "user", "content": prompt},
                    {"role": "system", "content": system_prompt},
                    ],
                temperature=app_settings['temperature'],
            )
            # If the request was successful, break out of the loop
            break
        except openai.error.AuthenticationError:
            # Handle authentication errors (e.g., invalid API key)
            Config.socketio.emit('log', {'data': 'Authentication Error. Check your OpenAI API Key!'}, room=str(1), namespace='/')
            break
        except (openai.error.APIError, openai.error.Timeout, openai.error.ServiceUnavailableError, ConnectionResetError) as e:  
            # Handle APIError, Timeout, and ServiceUnavailableError for retry
            wait_time = 2 * (attempt + 1)
            Config.socketio.emit('log', {'data': f'Encountered an issue with OpenAI connection. Waiting for {wait_time} seconds...'}, room=str(1), namespace='/')
            time.sleep(wait_time)
        except Exception as e:
            # Handle all other exceptions without retrying
            print(f"An exception occurred: {e}")


            break
    else:
        raise Exception("Maximum number of retries exceeded.")

    answer = response['choices'][0]['message']['content']
    return answer

### OPENAI FUNCTIONS ###
def openai_generic(app_settings, prompt, system_prompt):

    openai.api_key = app_settings['openai_key']

    max_retries = 15
    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(
                model=app_settings['model'],
                messages=[
                    {"role": "user", "content": prompt},
                    {"role": "system", "content": system_prompt},
                    ],
                temperature=app_settings['temperature'],
            )
            # If the request was successful, break out of the loop
            break
        except openai.error.AuthenticationError:
            # Handle authentication errors (e.g., invalid API key)
            Config.socketio.emit('log', {'data': 'Authentication Error. Check your OpenAI API Key!'}, room=str(1), namespace='/')
            break
        except (openai.error.APIError, openai.error.Timeout, openai.error.ServiceUnavailableError) as e:  
            # Handle APIError, Timeout, and ServiceUnavailableError for retry
            wait_time = 2 * (attempt + 1)
            Config.socketio.emit('log', {'data': f'Encountered an issue with OpenAI connection. Waiting for {wait_time} seconds...'}, room=str(1), namespace='/')
            time.sleep(wait_time)
        except Exception as e:
            # Handle all other exceptions without retrying
            print(f"An exception occurred: {e}")
            break
    else:
        raise Exception("Maximum number of retries exceeded.")

    answer = response['choices'][0]['message']['content']
    return answer

# Google Related Searches
def get_related_searches(query):
    BASE_URL = 'https://www.google.com/search?q={}'
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(BASE_URL.format(query), headers=headers)
        response.raise_for_status()  # Raises HTTPError if the HTTP request returned an unsuccessful status code
        
        # Check if Google is blocking the request by looking for the CAPTCHA div
        if 'Our systems have detected unusual traffic' in response.text:
            return "Error: Google has detected unusual traffic from this machine/network."

        soup = BeautifulSoup(response.content, 'html.parser')
        bres_div = soup.find('div', id='bres')

        if bres_div:
            related_searches = [a.get_text() for a in bres_div.select('a') if a.get('href', '').startswith('/search?sca_esv=')]
            return ', '.join(related_searches)
        else:
            return

    except requests.RequestException as e:
        Config.socketio.emit('log', {'data': f'Encountered an error with Google Search. \nMessage: {e}'}, room=str(1), namespace='/')
        return f"Error: Network error. Details: {e}"

    except Exception as e:
        Config.socketio.emit('log', {'data': f'Error: An unexpected error occurred. Details: {e}'}, room=str(1), namespace='/')
        return f"Error: An unexpected error occurred. Details: {e}"
  
def keyword_clusters(db, Category_Settings, app_settings, main_query, project_id):
    now = datetime.now()
    formatted_now = now.strftime("%d/%m/%Y %H:%M:%S")
    
    # Initial related searches
    initial_keywords_string = get_related_searches(main_query)
    Config.socketio.emit('log', {'data': f'{formatted_now}: Search Google for related searches'},room=str(project_id), namespace='/')
    
    if "Error" in initial_keywords_string:
        return {"error": initial_keywords_string}
    
    # Cleaning up the entire initial keywords string
    Config.socketio.emit('log', {'data': f'{formatted_now}: Cleaning keywords from brands or websites that are different from {app_settings["url"]}'},room=str(project_id), namespace='/')
    cleaned_initial_keywords_string = openaisearch(db, Category_Settings, app_settings, initial_keywords_string, main_query)
    cleaned_initial_keywords = [kw.strip() for kw in cleaned_initial_keywords_string.split(',')]
    
    
    # Dictionary to store results
    clusters = {}
    
    # Perform additional searches for each cleaned keyword
    for keyword in cleaned_initial_keywords:
        # Fetch related searches
        secondary_keywords_string = get_related_searches(keyword)
        Config.socketio.emit('log', {'data': f'{formatted_now}: Find related searches for {keyword}'},room=str(project_id), namespace='/')
        
        if "Error" in secondary_keywords_string:  # Ensure that we got a valid list of keywords
            continue

        # Clean secondary keywords
        cleaned_secondary_keywords = openaisearch(db, Category_Settings, app_settings, secondary_keywords_string, keyword)
        Config.socketio.emit('log', {'data': f'{formatted_now}: Clean secondary keywords'},room=str(project_id), namespace='/')
        
        clusters[keyword] = cleaned_secondary_keywords

    return clusters

def related_searches(app_settings, main_query, project_id):
    now = datetime.now()
    formatted_now = now.strftime("%d/%m/%Y %H:%M:%S")
    # Initial related searches
    initial_keywords_string = get_related_searches(main_query)
    Config.socketio.emit('log', {'data': f'{formatted_now}: Search Google for related searches'},room=str(project_id), namespace='/')
    
    if "Error" in initial_keywords_string:
        return {"error": initial_keywords_string}
    
    # Cleaning up the entire initial keywords string
    Config.socketio.emit('log', {'data': f'{formatted_now}: Cleaning keywords from brands or websites that are different from {app_settings["url"]}'},room=str(project_id), namespace='/')
    clusters = openaisearch(app_settings, initial_keywords_string, main_query)


    return clusters

### This function is used to clean up the keywords from brands or websites that are different from the website url
def is_already_linked(faq, brand, linked_brand):
    return brand in faq and linked_brand not in faq

def get_last_processed_category(db, Processed_category, project_id):
    try:
        last_category = db.session.query(Processed_category).filter(Processed_category.project_id == project_id).order_by(desc(Processed_category.category_id)).first()
        if last_category:
            return last_category.category_id
        else:
            return None
    except Exception as e:
        print(f"Error: {str(e)}")
        return None
    
### GET RELATED SEARCHES AND SECOND LEVEL RELATED SEARCHES ###
def keyword_subsequence(db, Category_Settings, app_settings, main_query, project_id):
    now = datetime.now()
    formatted_now = now.strftime("%d/%m/%Y %H:%M:%S")

    if isinstance(main_query, str):
        main_queries = [query.strip() for query in main_query.split(',')]
    else:  # assuming main_query is a list
        main_queries = [query.strip() for query in main_query]


    # Dictionary to store results
    clusters = {}

    # Iterate over each query in main_queries
    for query in main_queries:
        # Initial related searches
        initial_keywords_string = get_related_searches(query)
        Config.socketio.emit('log', {'data': f'{formatted_now}: Search Google for related searches'}, room=str(project_id), namespace='/')

        if "Error" in initial_keywords_string:
            continue
        
        # Cleaning up the entire initial keywords string
        Config.socketio.emit('log', {'data': f'{formatted_now}: Cleaning keywords from brands or websites that are different from {app_settings["url"]}'}, room=str(project_id), namespace='/')
        cleaned_initial_keywords_string = openaisearch(db, Category_Settings, app_settings, initial_keywords_string, query)
        cleaned_initial_keywords = [kw.strip() for kw in cleaned_initial_keywords_string.split(',')]

        # Perform additional searches for each cleaned keyword
        for keyword in cleaned_initial_keywords:
            # Fetch related searches
            secondary_keywords_string = get_related_searches(keyword)
            Config.socketio.emit('log', {'data': f'{formatted_now}: Find related searches for {keyword}'}, room=str(project_id), namespace='/')
            print(f"Find related searches for {keyword}")

            if "Error" in secondary_keywords_string:  # Ensure that we got a valid list of keywords
                clusters[keyword] = {"error": secondary_keywords_string}
                continue

            # Clean secondary keywords
            cleaned_secondary_keywords = openaisearch(db, Category_Settings, app_settings, secondary_keywords_string, keyword)
            Config.socketio.emit('log', {'data': f'{formatted_now}: Clean secondary keywords'}, room=str(project_id), namespace='/')
            print(f"Clean secondary keywords")

            clusters[keyword] = cleaned_secondary_keywords

    return clusters

### GET RELATED SEARCHES ###

def keywords_one_level(db, Category_Settings, app_settings, main_query, project_id):
    now = datetime.now()
    formatted_now = now.strftime("%d/%m/%Y %H:%M:%S")

    if isinstance(main_query, str):
        main_queries = [query.strip() for query in main_query.split(',')]
    else:  # assuming main_query is a list
        main_queries = [query.strip() for query in main_query]

    # Dictionary to store results
    clusters = {}

    # Iterate over each query in main_queries
    for query in main_queries:
        max_retries = 15
        retry_count = 0
        delay = 20  # initial delay in seconds

        while retry_count < max_retries:
            # Fetch related searches
            related_keywords_string = get_related_searches(query)
            #Config.socketio.emit('log', {'data': f'{formatted_now}: Search Google for related searches for {query}'}, room=str(project_id), namespace='/')

            if related_keywords_string is None or "Error" in related_keywords_string:
                if retry_count == max_retries - 1:  # if it's the last retry, store the error and break
                    clusters[query] = "error: " + related_keywords_string
                    break
                time.sleep(delay)  # wait for the delay before retrying
                delay *= 2  # double the delay for the next retry
                retry_count += 1
                continue

            # If successful, break out of the retry loop
            break

        if related_keywords_string is not None and "Error" not in related_keywords_string:
            # Cleaning up the related keywords string
            #Config.socketio.emit('log', {'data': f'{formatted_now}: Cleaning keywords from brands or websites that are different from {app_settings["url"]}'}, room=str(project_id), namespace='/')
            cleaned_related_keywords_string = openaisearch(db, Category_Settings, app_settings, related_keywords_string, query)
            cleaned_related_keywords = ', '.join([kw.strip() for kw in cleaned_related_keywords_string.split(',')])
            clusters[query] = cleaned_related_keywords

    return clusters



def has_products_in_category(app_settings, category_id):
    headers = {
        'X-CloudCart-ApiKey': app_settings['X-CloudCart-ApiKey'],
    }
    max_retries = 15
    retry_count = 0
    wait_time = 2  # Initial wait time in seconds

    while retry_count < max_retries:
        response = requests.get(f"{app_settings['url']}/api/v2/products", headers=headers, params={"filter[category_id]": category_id})

        if response.status_code == 200:
            response_data = response.json()
            total_products = response_data['meta']['page']['total']
            return total_products > 0
        else:
            # Debugging: print the status code and response text to get more info on the failure
            print(f"Retry {retry_count + 1} - Failed to check products for category ID {category_id}. Status code: {response.status_code}, Response: {response.text}")
            retry_count += 1
            time.sleep(wait_time)
            wait_time *= 2  # Double the wait time for the next retry

    # If the loop completes without success:
    print(f"Failed to check products for category ID {category_id} after {max_retries} retries.")
    return False

def fetch_image_url(app_url, image_id, headers):
    response = requests.get(f"{app_url}/api/v2/images/{image_id}", headers=headers)
    if response.status_code == 200:
        image_data = response.json()
        return image_data['data']['attributes']['thumbs'].get('300x300', '')
    else:
        # Debugging: print the status code and response text to get more info on the failure
        print(f"Failed to fetch image URL. Status code: {response.status_code}, Response: {response.text}")
    return

def get_product_details(product_id, app_settings):

    headers = {
        'X-CloudCart-ApiKey': app_settings['X-CloudCart-ApiKey'],
    }
    
    url = f"{app_settings['url']}/api/v2/products/{product_id}?include=category,vendor,property-options"
    response = requests.get(url, headers=headers)
    data = response.json()

    details = data['data']['attributes']

    vendor_name = ''
    vendor_slug = ''
    category_name = ''
    category_slug = ''
    property_option_values = {}

    if 'included' in data:
        included = data['included']
        # Extracting all property-option values from the included section
        property_option_values_raw = [inc for inc in included if inc['type'] == 'property-options']

        for option in property_option_values_raw:
            property_id = option['attributes']['property_id']
            value = option['attributes']['value']
            
            # Get property name
            property_name = getProperties(property_id, app_settings)
            
            if property_name in property_option_values:
                property_option_values[property_name].append(value)
            else:
                property_option_values[property_name] = [value]

        for inc in included:
            if inc['type'] == 'vendors':
                vendor_name = inc['attributes']['name']
                vendor_slug = inc['attributes']['url_handle']
            elif inc['type'] == 'categories':
                category_name = inc['attributes']['name']
                category_slug = inc['attributes']['url_handle']

    # Remove HTML tags from the description
    description_stripped = re.sub(r'<[^>]*>', '', details['description'])
    
    # Remove HTML tags from the short description, if it exists
    short_description = details['short_description']
    short_description_stripped = re.sub(r'<[^>]*>', '', short_description) if short_description else ''

    # Convert property_option_values to a single-line string
    property_option_values_str = ', '.join(f'{key}: {" ".join(values)}' for key, values in property_option_values.items())

    return {
        'name': details['name'],
        'url_handle': details['url_handle'],
        'price_from': "{:.2f}".format(details['price_from'] / 100) if details['price_from'] is not None else None,
        'short_description': short_description_stripped,
        'description': description_stripped,
        'vendor_name': vendor_name,
        'vendor_slug': vendor_slug, # 'vendor_slug' is used in the prompt to create a link to the vendor page
        'category_name': category_name,
        'category_slug': category_slug, # 'category_slug' is used in the prompt to create a link to the category page
        'property_option_values': property_option_values_str
    }

def getProperties(property_id, app_settings):
    headers = {
        'X-CloudCart-ApiKey': app_settings['X-CloudCart-ApiKey'],
    }
    url = f"{app_settings['url']}/api/v2/properties/{property_id}"
    response = requests.get(url, headers=headers)
    data = response.json()

    return data['data']['attributes']['name']





def get_wikipedia_url(title, lang=None):
    """Retrieve the URL of a Wikipedia page based on its title and optionally a language."""
    
    if lang:
        wikipedia.set_lang(lang)  # Set the language only if provided
    
    try:
        page = wikipedia.page(title)
        return page.url
    except wikipedia.DisambiguationError as e:
        print(f"Disambiguation error: {e.options}")
        return None
    except wikipedia.PageError:
        print(f"Page '{title}' does not exist.")
        return None
