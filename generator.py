# generator.py
import requests
import re
import openai
import urllib.parse
import csv
import json
import os
import validators
import time
from datetime import datetime
from flask_socketio import SocketIO, emit
from config import Config
import query
from sqlalchemy import func, desc


stop_process = {}

formatted_now = None
now = None

def reset_stop():
    print('Resetting the process...')
    global stop_process
    stop_process = False

socketio = None

def set_socketio(sio):
    global socketio
    print("Setting socketio:", sio)  # Debug line
    socketio = sio

    
# Initialize the settings as empty dictionaries
app_settings = {}
seo_settings = {}
prompt_settings = {}
short_description_settings = {}
  

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
    category_id = ''
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
        'category_id': details['category_id'],
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




def updateProduct(product_id, description, short_description, meta_description, app_settings, project_id):
    now = datetime.now()
    formatted_now = now.strftime("%d/%m/%Y %H:%M:%S")
    headers = {
        'X-CloudCart-ApiKey': app_settings['X-CloudCart-ApiKey'],
        'Content-Type': 'application/vnd.api+json',
    }
    url = f"{app_settings['url']}/api/v2/products/{product_id}"

    attributes = {
        key: value 
        for key, value in [
            ("description", description), 
            ("short_description", short_description),
            ("seo_description", meta_description)

        ] 
        if value  # This condition filters out empty values
    }   

    body = {
        "data": {
            "type": "products",
            "id": str(product_id),
            "attributes": attributes
        }
    }

    max_retries = 15

    for attempt in range(max_retries):
        try:
            response = requests.patch(url, data=json.dumps(body), headers=headers)
            if response.status_code in (429, 500, 502, 503):  # Retry for status codes 500 and 503
                raise Exception(f"Request to {url} failed with status code {response.status_code}. The response was: {response.text}")
            elif response.status_code != 200:  # For other non-200 status codes, fail immediately
                raise Exception(f"Request to {url} failed with status code {response.status_code}. The response was: {response.text}")
            
            return response.json()  # If request was successful, break out of the loop and return the response
        except Exception as e:
            if attempt < max_retries - 1:  # If it's not the last attempt, wait and then continue to the next iteration
                wait_time = 5 * (attempt + 1)
                Config.socketio.emit('log', {'data': f"{formatted_now}: Error occured at CloudCart. Waiting for {wait_time} seconds before retrying."},room=str(project_id), namespace='/')
                time.sleep(wait_time)
            else:  # On the last attempt, fail with an exception
                raise

def get_keywords(seo_settings, app_settings, product, project_id):
    global total_tokens_used_product
    total_tokens_used_product = 0

    now = datetime.now()
    formatted_now = now.strftime("%d/%m/%Y %H:%M:%S")
    if seo_settings['use_keywords'] == 0:
        return ''
    Config.socketio.emit('log', {'data': f"{formatted_now}: Generating keywords..."},room=str(project_id), namespace='/')
    #prompt = f'You are skilled SEO expert. Research ONLY the top {seo_settings["use_keywords"]} long-tail keywords, from the title of this product in {app_settings["language"]} language. Use the category \"{product["category_name"]}\" and the brand \"{product["vendor_name"]}\" only if you are absolutly sure that the information is critical for the top long-tail keyword. Please note that I want only the words without any other explanations from your side! Return the keywords by comma separated without quotes!\n'
    prompt = f'Your task is splited in 3 steps.\nFollow the steps from top to bottom:\n\nStep 1:\nCraft a list of the top {seo_settings["use_keywords"]} keywords using category \"{product["category_name"]}\", and brand \"{product["vendor_name"]}\" in {app_settings["language"]} language for SEO purpouses.\n\nStep 2:\nGenerate long-tail keywords, create a list of {seo_settings["use_keywords"]} long-tail keywords by using only the most relevant to: (\"{app_settings["niche"]}\" niche) Make sure each long-tail keyword contain one top keyword.\n\nStep 3:\nMake two Top-keywords and Long-tail keywords. All keywords must be separated by comma. Example: Top-keywords: keyword 1, keyword2, keyword 3\nLong-tail keywords: long-tail keyword 1, long-tail keyword 2, long-tail keyword 3. It is highly important to return the answer in the format of my example!'
    system_prompt = 'Return only step 3 without nameing it. Your answer must be structured the same way as my example!'
    max_retries = 15

    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(
                model=app_settings['model'],
                messages=[
                    {"role": "user", "content": prompt},
                    {"role": "system", "content": system_prompt}
                    ],
                temperature=app_settings['temperature'],
            )

            total_tokens_used_product += response['usage']['total_tokens']

            # If the request was successful, break out of the loop
            break
        except openai.error.AuthenticationError:
            # Handle authentication errors (e.g., invalid API key)
            Config.socketio.emit('log', {'data': 'Authentication Error. Check your OpenAI API Key!'}, room=str(1), namespace='/')
            break
        except (openai.error.APIError, openai.error.Timeout, openai.error.ServiceUnavailableError) as e:  
            #Handle APIError, Timeout, and ServiceUnavailableError for retry
            wait_time = 2 * (attempt + 1)
            Config.socketio.emit('log', {'data': f"{formatted_now}: Issue occured at OpenAI. Waiting for {wait_time} seconds before retrying."},room=str(project_id), namespace='/')
            print(f"Encountered an error: {e.error}. Waiting for {wait_time} seconds before retrying.")
            time.sleep(wait_time)
        except Exception as e:
            # Handle all other exceptions without retrying
            print(f"An exception occurred: {e}")
            break
    else:
        raise Exception("Maximum number of retries exceeded.")

    # Do something with the response, e.g., print the message content
    return(response['choices'][0]['message']['content'])

def generate_meta_description(product_dict, prompt_settings, app_settings, seo_settings, description, project_id):
    global total_tokens_used_product
    total_tokens_used_product = 0

    now = datetime.now()
    formatted_now = now.strftime("%d/%m/%Y %H:%M:%S")
    if description is None:
        description = ''
    if seo_settings.get('use_keywords', 0) == 0:
        prompt = f'You are skilled SEO expert at the online store: {app_settings["url"]}. Craft a meta description that effectively communicates the unique value proposition from the product desctiption: {description}. Write it in {app_settings["language"]} language, and the meta descritpion text should entices users to click on our website in search results by using emoji and other symbols (here is an example of good meta description: "Shop for High Heels Under 500 in India * Buy latest range of High Heels Under 500 at Myntra* Free Shipping # COD * Easy returns and exchanges."). The lenght of the meta description should be no more than 140 - 150 character range\n'
    else:
        prompt = f'You are skilled SEO expert at the online store: {app_settings["url"]}. Craft a meta description that effectively communicates the unique value proposition from the product desctiption: {description}. Be sure to use the right keywords ({seo_settings["use_keywords"]})in your meta description that are the most relevant. Write it in {app_settings["language"]} language, and the meta descritpion text should entices users to click on our website in search results by using emoji and other symbols (here is an example of good meta description: "Shop for High Heels Under 500 in India * Buy latest range of High Heels Under 500 at Myntra* Free Shipping # COD * Easy returns and exchanges."). The lenght of the meta description should be no more than 140 - 150 character range\n'
    
    if app_settings['print_prompt']:
        Config.socketio.emit('log', {'data': f"{formatted_now}: Meta description prompt: {prompt}"},room=str(project_id), namespace='/')
        return(prompt)
    
    max_retries = 15

    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(
                model=app_settings['model'],
                messages=[
                    {"role": "user", "content": prompt}
                                                    ],
                temperature=app_settings['temperature'],
            )
            
            total_tokens_used_product += response['usage']['total_tokens']

            # If the request was successful, break out of the loop
            break
        except openai.error.AuthenticationError:
            # Handle authentication errors (e.g., invalid API key)
            Config.socketio.emit('log', {'data': 'Authentication Error. Check your OpenAI API Key!'}, room=str(1), namespace='/')
            break
        except (openai.error.APIError, openai.error.Timeout, openai.error.ServiceUnavailableError) as e:  
            #Handle APIError, Timeout, and ServiceUnavailableError for retry
            wait_time = 2 * (attempt + 1)
            Config.socketio.emit('log', {'data': f"{formatted_now}: Error occured at OpenAI. Waiting for {wait_time} seconds before retrying."},room=str(project_id), namespace='/')
            print(f"Encountered an error: {e.error}. Waiting for {wait_time} seconds before retrying.")
            time.sleep(wait_time)
        except Exception as e:
            # Handle all other exceptions without retrying
            print(f"An exception occurred: {e}")
            break
    else:
        raise Exception("Maximum number of retries exceeded.")

    # Do something with the response, e.g., print the message content
    return response

def generate_short_description(product_dict, prompt_settings, description, app_settings, seo_settings, short_description_settings, project_id, prompt):
    global total_tokens_used_product
    total_tokens_used_product = 0
    
    now = datetime.now()
    formatted_now = now.strftime("%d/%m/%Y %H:%M:%S")
    if description is None:
        description = ''
    
    if app_settings['print_prompt']:
        Config.socketio.emit('log', {'data': f"{formatted_now}: Description prompt: {prompt}"},room=str(project_id), namespace='/')
        return
    max_retries = 15

    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(
                model=app_settings['model'],
                messages=[
                    {"role": "user", "content": prompt}
                                                    ],
                temperature=app_settings['temperature'],
            )

            total_tokens_used_product += response['usage']['total_tokens']

            # If the request was successful, break out of the loop
            break
        except openai.error.AuthenticationError:
            # Handle authentication errors (e.g., invalid API key)
            Config.socketio.emit('log', {'data': 'Authentication Error. Check your OpenAI API Key!'}, room=str(1), namespace='/')
            break
        except (openai.error.APIError, openai.error.Timeout, openai.error.ServiceUnavailableError) as e:  
            #Handle APIError, Timeout, and ServiceUnavailableError for retry
            wait_time = 2 * (attempt + 1)
            Config.socketio.emit('log', {'data': f"{formatted_now}: Problem occured at OpenAI. Waiting for {wait_time} seconds before retrying."},room=str(project_id), namespace='/')
            print(f"Encountered an error: {e.error}. Waiting for {wait_time} seconds before retrying.")
            time.sleep(wait_time)
        except Exception as e:
            # Handle all other exceptions without retrying
            print(f"An exception occurred: {e}")
            break
    else:
        raise Exception("Maximum number of retries exceeded.")

    # Do something with the response, e.g., print the message content
    return response

def create_prompt(product, prompt_settings, app_settings, seo_settings, project_id):
    now = datetime.now()
    formatted_now = now.strftime("%d/%m/%Y %H:%M:%S")
    # Initialize an empty string for the prompt
    prompt = ''
    category_name_link = ''
    vendor_name_link = ''
    keyword_product_link = ''
    link_keyword_to_product = ''
    keywords_quoted = ''
    keywords = ''
    available_links = f'{app_settings["url"]}/category/{product["category_slug"]}, {app_settings["url"]}/vendor/{product["vendor_slug"]}, {app_settings["url"]}/category/{product["category_slug"]}?vendors={product["vendor_slug"]}'
    


    # Check if SEO package is in use
    if app_settings['use_seo_package']:
        # Create an anchor tag with product name and URL
        if seo_settings['link_to_product']:
            product_name_link = f'<a href="{app_settings["url"]}/product/{product["url_handle"]}" target="_blank" alt="put long-tail keyword">put keyword here</a>\n'
        if seo_settings['link_to_category']:
            category_name_link = f'<a href="{app_settings["url"]}/category/{product["category_slug"]}" target="_blank" alt="put keyword here">put keyword here</a>\n'
        if seo_settings['link_to_vendor'] and product['vendor_slug']:
            vendor_name_link = f'<a href="{app_settings["url"]}/vendor/{product["vendor_slug"]}" target="_blank" alt="put keyword here">put keyword here</a>\n'
        if seo_settings['link_to_more_from_same_vendor_and_category'] and product['vendor_slug']:
            more_from_same_vendor_and_category_link = f'<a href="{app_settings["url"]}/category/{product["category_slug"]}?vendors={product["vendor_slug"]}" target="_blank" alt="{product["category_name"]} - {product["vendor_name"]}"> give the user the option to see more from \"{product["vendor_name"]}\"</a>\n'
        else:
            more_from_same_vendor_and_category_link = f'<a href="{app_settings["url"]}/category/{product["category_slug"]}" target="_blank" alt="{product["category_name"]}"> give the user the option to see more from \"{product["category_name"]}\"</a>\n'
        ####### GENERATE KEYWORDS #######
        if seo_settings['use_keywords'] != 0:
            generated_keywords = get_keywords(seo_settings, app_settings, product, project_id)
            keywords = generated_keywords.replace('"', '')
        if seo_settings['link_keyword_to_product']:
            #link_keyword_to_product = f"In addition, you must make at least {seo_settings['link_keyword_density']} links at the text to that keywords that are most relevant to the generated text. You can use the following links: {keyword_product_link} {category_name_link} {vendor_name_link}\n"
            #link_keyword_to_product = f"Important! Minimum {seo_settings['link_keyword_density']} of the keywords must be linked on a random basis. You can use the following links more than {seo_settings['link_keyword_density']} times: {keyword_product_link} {category_name_link} {vendor_name_link}.\n"
            #link_keyword_to_product = f"Make links not less than {seo_settings['link_keyword_density']} only on Top-keywords (do not link lang-tail keywords)! You must use the links: {keyword_product_link} {category_name_link} {vendor_name_link}"
            link_keyword_to_product = f"Find the top keywords from your ready description and add minimum {seo_settings['link_keyword_density']} links of this list: {available_links}. There is no problem to have one link several times\n"
        #################################

    # Main instructions
    prompt += f"Your task for product description is splited in steps. Follow strictly the steps from here to the end!"
    prompt += f"As a {prompt_settings['purpouse']} copywriter, writing in {app_settings['language']} language, craft a description for the product \"{product['product_name']}\". This product description will be published online at \"{app_settings['website_name']}\" - \"{app_settings['url']}\" (do not invite the user to go to the store, he is already there!).\n"
    prompt += f"The product is published at category: {product['category_name']} ({app_settings['url']}/category/{product['category_slug']}) and the vendor is {product['vendor_name']} ({app_settings['url']}/vendor/{product['vendor_slug']}).\n"
    if prompt_settings['property_option_values']:
        prompt += f"{product['product_name']} has the following features, which are one of the most important parts of the text: {product['property_option_values']}\n"
        if prompt_settings['use_feature_desc']:
            prompt += f"Based on product properties/features you must write a feature/benefit dichotomy description. For example, stating that a dishwasher applies high heat and water pressure (or worse, providing numbers with no context) doesn't tell the reader anything. These are features, and they resonate with the reader much better when you pair them with their benefit. In this case, the benefit might be that buying this dishwasher will liberate them from having to remove food residue and stains by hand."
    if prompt_settings['short_description']:
        prompt += f"Product short description is: \"{product['short_description']}\";\n"
    if prompt_settings['description']:
        prompt += f"Product description is: \"{product['description']}\"\n"
    if prompt_settings['use_hidden_benefit']:
        prompt += f"craft a hidden benefit/feature based on the properties and description of the product!.\n"
    if prompt_settings['use_interesting_fact']:
        prompt += f"Craft an interesting fact based on the description that will add value to the product.\n"
    if app_settings['use_seo_package']:
        prompt += f"Avoid superfluous words. Avoid Generic Writing, instead, employ Unique features and benefits, The 'What' of what your product can do for them, Explanation of the specific ways the product will improve their lives. Don't use the passive voice.\n"
    if prompt_settings["additional_instructions"]:
        prompt += f"Additional important instructions: {prompt_settings['additional_instructions']};\n\n"
    if prompt_settings.get('price_from'):
        # Check if 'show_price' is in prompt_settings and is True
        if prompt_settings.get('show_price'):
            # Check if 'price_from' and 'currency' exist in the product and app_settings respectively
            if product.get('price_from') and app_settings.get('currency'):
                prompt += f"Product price: {product['price_from']} {app_settings['currency']} "
            else:
                prompt += "Do not mention the product price but if you decide you can use some words about the benefit of the price!"     
        # Check if 'price_from' is in the product and 'free_delivery_over' is in app_settings and both are not None
        if product.get('price_from') and app_settings.get('free_delivery_over') and \
        float(product['price_from']) > app_settings['free_delivery_over']:
            # Check if 'mention_free_delivery_price' is in app_settings and is True
            if app_settings.get('mention_free_delivery_price'):
                # Check if 'currency' is in app_settings and is not None
                if app_settings.get('currency'):
                    prompt += f"The product that you are writing description might be eligible for free delivery for orders over {app_settings['free_delivery_over']} {app_settings['currency']} but advice the customer to check it when they are purchasing;\n"
            else:
                prompt += "The product that you are writing description might be eligible for free delivery but advice the customer to check it when they are purchasing.\n"

    
    # SEO and Keywords instructions
    if app_settings['use_seo_package']:
        prompt += f"\nStep 2\nImplementing the best SEO technics and practises by Google is a must. You must follow the following SEO rules:\n"
        if seo_settings['use_free_keywords'] != '':
            keyword_split = seo_settings['use_free_keywords'].split(',')
            keywords_quoted = ', '.join(f'{keyword}' for keyword in keyword_split)
        if seo_settings['use_keywords'] != 0:
            #use_keywords = f"All keywords should be used in the most natural way accros the generated description (not only at the bottom of the text). For example at the beginning of the text, at the middle and at the end. The description should contains the following keywords: {keywords}. Use each combination not less than {seo_settings['keywords_density']} times.\n"
            #use_keywords = f"Your product description must contain {seo_settings['keywords_density']} times each of this ({keywords}, {keywords_quoted}) keywords {link_keyword_to_product}. Spread them naturally across the generated description (not only at the bottom of the text). For example at the beginning of the text, at the middle, and at the end. "
            use_keywords = f"Use the following keywords into your description {seo_settings['keywords_density']} times each. The keywords are: {keywords}, {keywords_quoted}. The keywords must be used across the generated description. For example at the beginning of the text, at the middle, and at the end of the text. "
            prompt += f'{use_keywords}'
        elif seo_settings['use_free_keywords'] != '':
            use_keywords = f"Use the following keywords into your description {seo_settings['keywords_density']} times each. The keywords are: {keywords_quoted}. The keywords must be used across the generated description. For example at the beginning of the text, at the middle, and at the end of the text. "
            prompt += f'{use_keywords}'
        if seo_settings['link_to_product']:
            prompt += f"{product_name_link} "
        if seo_settings['link_to_category']:
            prompt += f"Use the link to the category {category_name_link} "
            ### Check if {product['vendor_slug']} is not empty
        if seo_settings['link_to_vendor'] and product['vendor_slug']:
            prompt += f"Also add a link to the vendor listing page {vendor_name_link} "
        if seo_settings['link_to_more_from_same_vendor_and_category'] and product['vendor_slug']:
            prompt += f"In addition add a link to find more products from category: {product['category_name']} and brand: {product['vendor_name']}: {more_from_same_vendor_and_category_link}\n"
        else:
            prompt += f"In addition add a link to find more products from category: {product['category_name']}: {more_from_same_vendor_and_category_link}\n"
        if seo_settings['link_keyword_to_product']:
            prompt += f"\nStep 3\nAdd links to generated description\n"
            prompt += f'{link_keyword_to_product}'

        if seo_settings['e_e_a_t']:
            prompt += f"\nStep 4\nKnowing the E-E-A-T standart craft the entire product description by following Google guidelines:\n"
            prompt += f"Does the content demonstrate first-hand experience?\nDoes the content demonstrate in-the-field experience?\nHow well does the content share a personal experience, perspective, or feelings on a topic?\nHow well does the content speak from a first-person perspective?\nDoes content also demonstrate that it was produced with some degree of experience, such as actual product use, or communicating what a person experienced?\nHow original is the content?\nDoes this content demonstrate a depth of expertise in this topic?\nThe goals:\n1. Experience: goal minimum 9 \n2. Effort: goal minimum 9 \n3. Quality: no less than 10.\n4. Uniqueness: 8 .\n5. Depth: 9.\nThe overall score must be no more than 9 out of 10!!!\n"

    prompt += f"\nFinal Step.\nOutput the final text wihtout any reference from your instructions. Do not name the steps nor anything that is not related to the text\n"
    prompt += f"The lenght of the content must be {app_settings['length']} words.\n\n"
    return prompt

def create_prompt_short_description(product, prompt_settings, app_settings, seo_settings, short_description_settings, project_id):
    # Initialize an empty string for the prompt
    prompt = ''

    # Check if SEO package is in use
        # Main instructions
    prompt += f'Strictly follow the instructions step by step! \nMain instructions: \n'
    prompt += f"You are {short_description_settings['short_purpose']} copywriter at {app_settings['website_name']} that works in \"{app_settings['niche']}\". You are writing and adapting this short description in {short_description_settings['short_language']} language.\n"
    prompt += f"The short description must be in no more than {short_description_settings['short_length']} words and it must highlight the product bennefits only.\n"
    '''
    if short_description_settings['use_seo_package']:
        # Create an anchor tag with product name and URL
        if short_description_settings['link_to_product']:
            product_name_link = f'<a href="{app_settings["url"]}/product/{product["url_handle"]}" target="_blank" alt="rewrite in {app_settings["language"]} language the alt title: \"{product["product_name"]}\"">put the product title here</a>'
        if short_description_settings['link_to_category']:
            category_name_link = f'<a href="{app_settings["url"]}/category/{product["category_slug"]}" target="_blank" alt="rewrite in {app_settings["language"]} language, the alt title: \"{product["category_name"]}\"">put the category name here</a>'
        if short_description_settings['link_to_vendor']:
            vendor_name_link = f'<a href="{app_settings["url"]}/vendor/{product["vendor_slug"]}" target="_blank" alt="{product["vendor_name"]}">put the vendor name here</a>'
        if short_description_settings['link_to_more_from_same_vendor_and_category']:
            more_from_same_vendor_and_category_link = f'<a href="{app_settings["url"]}/category/{product["category_slug"]}?vendors={product["vendor_slug"]}" target="_blank" alt="rewrite in {app_settings["language"]} language the alt title: \"{product["vendor_name"]} - {product["category_name"]}\"">give the user the option to see more from \"{product["vendor_name"]}\"</a>'
        if short_description_settings['use_keywords'] != 0:
            keywords = get_keywords(seo_settings, app_settings, product)
        if short_description_settings['link_keyword_to_product']:
            keyword_product_link = f'<a href="{app_settings["url"]}/product/{product["url_handle"]}" target="_blank" alt="rewrite in {app_settings["language"]} language the alt title: \"{product["product_name"]}\""> put the keywords here </a>'
    
    # SEO and Keywords instructions
    if short_description_settings['use_seo_package']:
        prompt += f"This part is highly important! Stryctly follow the SEO and keywords instructions: \n"
        if short_description_settings['use_keywords'] != 0:
            prompt += f"All keywords should be used in the most natural way accros the generated description. For example at the beginning of the text, at the middle and at the end. The description should contains the following keywords: {keywords}. Use each combination not less than {seo_settings['keywords_density']} times. \n"
        if short_description_settings['use_free_keywords'] != '':
            free_keywords = f'and you must combine it with the best relevant keywords from here: \"{seo_settings["use_free_keywords"]}\"'
            prompt += f'You are skilled SEO expert. Research ONLY the top {seo_settings["use_keywords"]} long-tail keywords, from the title of this product {free_keywords} in {app_settings["language"]} language. Use the category \"{product["category_name"]}\" and the brand \"{product["vendor_name"]}\" only if you are absolutly sure that the information is critical for the top long-tail keyword. Please note that I want only the words without any other explanations from your side! Return the keywords by comma separated. \n'
        if short_description_settings['link_keyword_to_product']:
            prompt += f"In addition, you must make at least {seo_settings['link_keyword_density']} links to that keywords with this link: {keyword_product_link}. \n"
        if short_description_settings['link_to_product']:
            prompt += f"add this link to one of the product titles: {product_name_link}, "
        if short_description_settings['link_to_category']:
            prompt += f"add this link to one of the category names: {category_name_link}, "
        if short_description_settings['link_to_vendor']:
            prompt += f"Add this link to one of the vendor names: {vendor_name_link}, "
        if short_description_settings['link_to_more_from_same_vendor_and_category']:
            prompt += f"Add a link to find more products from category: {product['category_name']} and brand: {product['vendor_name']}: {more_from_same_vendor_and_category_link}. \n"
        '''
    # Product information instructions
    prompt += f"\n Product information instructions: \n"
    if short_description_settings['short_product_name']:
        prompt += f"- Use the product name: \"{product['product_name']}\"; \n"      
        # Check if 'price_from' is in the product and 'free_delivery_over' is in app_settings and both are not None
    # Product specifications instructions
    if short_description_settings['short_short_description']:
        prompt += f"- Use this short description to rewrite your new short description: \"{product['short_description']}\";\n"
    if short_description_settings['short_vendor_name']:
        prompt += f"- The brand is: \"{product['vendor_name']}\";\n"
    if short_description_settings['short_category_name']:
        prompt += f"- Category is: \"{product['category_name']}\" (you must use it only for reference for the description but not directly);\n"
    if short_description_settings['short_property_option_values']:
        prompt += f"- Use product characteristics: \"{product['property_option_values']}\". Highlight only the most valuable product characteristics.\n"
    if short_description_settings['short_additional_instructions']:
        prompt += f"- Additional prompt instructions: \"{short_description_settings['short_additional_instructions']}\".\n"

    return prompt


def get_all_products(db, Statistics, Processed, Project, app_settings, seo_settings, prompt_settings, short_description_settings, project_id):
    global total_tokens_used_product
    total_tokens_used_product = 0
    
    now = datetime.now()
    formatted_now = now.strftime("%d/%m/%Y %H:%M:%S")

    project = Project.query.get(project_id)
    project = db.session.get(Project, project_id)
    if project:
        project.in_progress = True
        db.session.commit()

    stop_process[project_id] = False
    last_processed_product_id, last_page_url = get_last_processed_product(db, Processed, project_id)
    all_product_ids = []

    Config.socketio.emit('log', {'data': f'{formatted_now}: Started... '},room=str(project_id), namespace='/')
 
    # If there is a last processed product, start processing from the next product
    if last_processed_product_id and last_page_url:
        url = last_page_url
    else:
        # If there is no last processed product, build the base URL and filters as before
        url = f"{app_settings['url']}/api/v2/products"
    
    if not validators.url(url):
        raise Exception("The URL provided in 'app_settings' is not valid")

    # Set the OpenAI key
    openai.api_key = app_settings['openai_key']

    # Build the filters based on app_settings
    product_count = 0  # add a counter for products processed
    test_mode = app_settings['test_mode']  # Get the test mode value from settings
    description = ''  # Initialize the description variable
    short_description = ''  # Initialize the short_description variable
    meta_description = ''  # Initialize the meta_description variable
    enable_product_description = app_settings['enable_product_description']
    enable_generate_meta_description = app_settings['enable_generate_meta_description']  # Get the enable_generate_meta_description value from settings
    enable_product_short_description = app_settings['enable_product_short_description']  # Get the enable_generate_short_description value from settings

    headers = {
        'X-CloudCart-ApiKey': app_settings['X-CloudCart-ApiKey'],
    }

    ##############################################
    ########## PROCESS SPECIFIC PRODUCT ##########
    ##############################################

    if app_settings.get('specific_product'):
        
        url = f"{app_settings['url']}/api/v2/products"
        url += '/' + app_settings['specific_product']
        ################# PROCESS SPECIFIC PRODUCT #################

        if stop_process.get(project_id, False):
            Config.socketio.emit('log', {'data': 'Process stopped by user.'},room=str(project_id), namespace='/')
            stop(project_id)  # Stop processexit
            project = db.session.get(Project, project_id)
            if project:
                project.in_progress = False
                db.session.commit()
            return

        response = requests.get(url, headers=headers)
        data = response.json()

        if 'data' in data:

            product_id = data['data']['id']
            task_id = None
            details = get_product_details(product_id, app_settings)

            # Skip product with short descriptions
            if app_settings['skip_products_with_description'] > 0 and len(details['description'].split()) > app_settings['skip_products_with_description']:
                Config.socketio.emit('log', {'data': f"{formatted_now}: \nProduct: {details['name']} has more than {app_settings['skip_products_with_description']} words.\nSkipped product..."},room=str(project_id), namespace='/')
                return
            
            # Build the product dictionary
            product_dict = {
                'product_id': product_id,
                'product_name': details['name'],
                'url_handle': details['url_handle'],
                'price_from': details['price_from'],
                'short_description': details['short_description'],
                'description': details['description'],
                'vendor_name': details['vendor_name'],
                'vendor_slug': details['vendor_slug'],
                'category_id': details['category_id'],
                'category_name': details['category_name'],
                'category_slug': details['category_slug'],
                'property_option_values': details['property_option_values']
            }

            ############## CHECK IF PRODUCT DESCRIPTION IS ENABLED ##############
            if enable_product_description:
                response = None
                # Create a prompt for each product




                prompt = create_prompt(product_dict, prompt_settings, app_settings, seo_settings, project_id)
                if app_settings['print_prompt']:
                    Config.socketio.emit('log', {'data': f"{formatted_now}: \nPrompt message: \n######################################\n{prompt}######################################\n"},room=str(project_id), namespace='/')
                    Config.socketio.emit('log', {'data': f'\nProcess completed...'},room=str(project_id), namespace='/')
                    project = db.session.get(Project, project_id)
                    if project:
                        project.in_progress = False
                        db.session.commit()
                    return(prompt)
                Config.socketio.emit('log', {'data': f"{formatted_now}: Processing product with ID: {product_dict['product_id']}"},room=str(project_id), namespace='/')
                
                # Get the response from OpenAI
                max_retries = 15

                for attempt in range(max_retries):
                    now = datetime.now()
                    formatted_now = now.strftime("%d/%m/%Y %H:%M:%S")
                    try:
                        response = openai.ChatCompletion.create(
                            model=app_settings['model'],
                            messages=[
                                {"role": "user", "content": prompt},
                                {"role": "system", "content": "You must add html tags to the text and you must bold important parts and words! Do not use H1 tags, use H2 and H3 tags instead! The links at the text should be accross the entire text not only at the end!"},
                            ],
                            temperature=app_settings['temperature'],
                        )
                        total_tokens_used_product += response['usage']['total_tokens']

                        # If the request was successful, break out of the loop
                        break
                    except openai.error.AuthenticationError:
                        # Handle authentication errors (e.g., invalid API key)
                        Config.socketio.emit('log', {'data': 'Authentication Error. Check your OpenAI API Key!'}, room=str(1), namespace='/')
                        break
                    except (openai.error.APIError, openai.error.Timeout, openai.error.ServiceUnavailableError) as e:  
                        #Handle APIError, Timeout, and ServiceUnavailableError for retry
                        wait_time = 2 * (attempt + 1)
                        Config.socketio.emit('log', {'data': f"{formatted_now}: Error occured at OpenAI. Waiting for {wait_time} seconds before retrying."},room=str(project_id), namespace='/')
                        print(f"Encountered an error: {e.error}. Waiting for {wait_time} seconds before retrying.")
                        time.sleep(wait_time)
                    except Exception as e:
                        # Handle all other exceptions without retrying
                        print(f"An exception occurred: {e}")
                        break
                else:
                    raise Exception("Maximum number of retries exceeded.")

                description = response['choices'][0]['message']['content']


                ##### TEST MODE ONLY #####
                if test_mode != 0:

                    if stop_process.get(project_id, False):
                        stop(project_id)  # Stop process
                        project = db.session.get(Project, project_id)
                        if project:
                            project.in_progress = False
                            db.session.commit()
                        Config.socketio.emit('log', {'data': 'Process stopped by user.'},room=str(project_id), namespace='/')
                        return
                    
                    # Calculate cost
                    cost = cost_statistics_all(response, app_settings)                
                    task_id = "product"
                    ###### Save statistics ###### 
                    import query

                    query.statistics(db, Statistics, project_id, product_id, app_settings, task_id, response, cost, test_mode=1)
                    
                    ###### SAVE PROCESSED PRODUCT ######
                    url_handle = app_settings['url'] + '/product/' + product_dict['url_handle']
                    title = product_dict['product_name']

                    # Query the Processed_category table for the column token_count for this category
                    record = db.session.query(Processed).filter_by(project_id=project_id, record_id=product_id).first()
                    current_token_count = record.token_count if record else 0

                    if current_token_count is None or current_token_count == 0:
                        token_count = total_tokens_used_product
                        import query

                        #query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, description=description, url_handle=url_handle, title=title)
                    else:
                        token_count = current_token_count + total_tokens_used_product

                    
                    query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, description=description, url_handle=url_handle, token_count=token_count, title=title)
                    total_tokens_used_product = 0

                    ####################################

                    ###### Emit the description to the client ######
                    Config.socketio.emit('log', {'data': f'\n{description}\n'},room=str(project_id), namespace='/')
    

                ##### LIVE MODE #####
                if test_mode == 0:

                    if stop_process.get(project_id, False):
                        stop(project_id)  # Stop process
                        project = db.session.get(Project, project_id)
                        if project:
                            project.in_progress = False
                            db.session.commit()
                        Config.socketio.emit('log', {'data': 'Process stopped by user.'},room=str(project_id), namespace='/')
                        return

                    # Calculate cost
                    cost = cost_statistics_all(response, app_settings) 
                    
                    ###### Save statistics ######
                    import query

                    task_id = "product"
                    query.statistics(db, Statistics, project_id, product_id, app_settings, task_id, response, cost, test_mode=0)
                    
                    # Update the product description
                    updateProduct(product_id, description, short_description, meta_description, app_settings, project_id)
                    
                    ###### SAVE PROCESSED PRODUCT ######
                    url_handle = app_settings['url'] + '/product/' + product_dict['url_handle']
                    title = product_dict['product_name']

                    # Query the Processed_category table for the column token_count for this category
                    record = db.session.query(Processed).filter_by(project_id=project_id, record_id=product_id).first()
                    current_token_count = record.token_count if record else 0

                    if current_token_count is None or current_token_count == 0:
                        token_count = total_tokens_used_product
                        import query

                        #query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, description=description, url_handle=url_handle, title=title)
                    else:
                        token_count = current_token_count + total_tokens_used_product


                    query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, description=description, url_handle=url_handle, published=1, token_count=token_count, title=title)
                    total_tokens_used_product = 0
                    ####################################
                    
                    Config.socketio.emit('log', {'data': f"{formatted_now}: Product: {product_dict['product_name']} with ID: {product_dict['product_id']} is updated..."},room=str(project_id), namespace='/')
            
            ############## CHECK IF PRODUCT SHORT DESCRIPTION IS ENABLED ##############
            if enable_product_short_description:
                response = None
                prompt = None

                prompt = create_prompt_short_description(product_dict, prompt_settings, app_settings, seo_settings, short_description_settings, project_id)
                if app_settings['print_prompt']:
                    Config.socketio.emit('log', {'data': f"{formatted_now}: \nPrompt message: \n######################################\n{prompt}######################################\n"},room=str(project_id), namespace='/')
                    project = db.session.get(Project, project_id)
                    if project:
                        project.in_progress = False
                        db.session.commit()
                    return(prompt)
                # Create a prompt for each product
                
                response = generate_short_description(product_dict, prompt_settings, description, app_settings, seo_settings, short_description_settings, project_id, prompt)

                
                Config.socketio.emit('log', {'data': f'\nShort description generation for {product_dict["product_name"]} with ID: {product_dict["product_id"]}'},room=str(project_id), namespace='/')
                short_description = response['choices'][0]['message']['content']

                ##### TEST MODE ONLY #####
                if test_mode != 0:

                    if stop_process.get(project_id, False):
                        stop(project_id)  # Stop process
                        Config.socketio.emit('log', {'data': 'Process stopped by user.'},room=str(project_id), namespace='/')
                        project = db.session.get(Project, project_id)
                        if project:
                            project.in_progress = False
                            db.session.commit()
                        return             

                    # Calculate cost
                    cost = cost_statistics_all(response, app_settings)                

                    ###### Save statistics ###### 
                    task_id = "short_description"
                    import query
                    query.statistics(db, Statistics, project_id, product_id, app_settings, task_id, response, cost, test_mode=1)
                    ###### SAVE PROCESSED PRODUCT ######
                    url_handle = app_settings['url'] + '/product/' + product_dict['url_handle']
                    title = product_dict['product_name']

                    # Query the Processed_category table for the column token_count for this category
                    record = db.session.query(Processed).filter_by(project_id=project_id, record_id=product_id).first()
                    current_token_count = record.token_count if record else 0

                    if current_token_count is None or current_token_count == 0:
                        token_count = total_tokens_used_product
                        import query

                        #query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, description=description, url_handle=url_handle, title=title)
                    else:
                        token_count = current_token_count + total_tokens_used_product
 

                    query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, short_description=short_description, url_handle=url_handle, token_count=token_count, title=title)
                    total_tokens_used_product = 0
                    ####################################
         
                    ###### Emit the description to the client ######
                    Config.socketio.emit('log', {'data': f'\n{short_description}\n'},room=str(project_id), namespace='/')

                ##### LIVE MODE #####
                if test_mode == 0:

                    if stop_process.get(project_id, False):
                        stop(project_id)  # Stop process
                        Config.socketio.emit('log', {'data': 'Process stopped by user.'},room=str(project_id), namespace='/')
                        project = db.session.get(Project, project_id)
                        if project:
                            project.in_progress = False
                            db.session.commit()
                        return 

                    # Calculate cost
                    cost = cost_statistics_all(response, app_settings) 
                    
                    ###### Save statistics ######
                    task_id = "short_description"
                    import query
                    query.statistics(db, Statistics, project_id, product_id, app_settings, task_id, response, cost, test_mode=0)
                    
                    # Update the short description
                    updateProduct(product_id, description, short_description, meta_description, app_settings, project_id)
                    
                    ###### SAVE PROCESSED PRODUCT ######
                    url_handle = app_settings['url'] + '/product/' + product_dict['url_handle']
                    title = product_dict['product_name']

                    # Query the Processed_category table for the column token_count for this category
                    record = db.session.query(Processed).filter_by(project_id=project_id, record_id=product_id).first()
                    current_token_count = record.token_count if record else 0

                    if current_token_count is None or current_token_count == 0:
                        token_count = total_tokens_used_product
                        import query

                        #query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, description=description, url_handle=url_handle, title=title)
                    else:
                        token_count = current_token_count + total_tokens_used_product

                    query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, short_description=short_description, url_handle=url_handle, token_count=token_count, published=1, title=title)
                    total_tokens_used_product = 0
                    ####################################
         
                    Config.socketio.emit('log', {'data': f"{formatted_now}: Product short description for: {product_dict['product_name']} with ID: {product_dict['product_id']} is updated..."},room=str(project_id), namespace='/')

            ############## CHECK IF META DESCRIPTION IS ENABLED ##############
            if enable_generate_meta_description:
                response = None
                # Create a prompt for each product

                response = generate_meta_description(product_dict, prompt_settings, app_settings, seo_settings, description, project_id)
                if app_settings["print_prompt"] is True:
                    project = db.session.get(Project, project_id)
                    if project:
                        project.in_progress = False
                        db.session.commit()
                    return
                Config.socketio.emit('log', {'data': f'Meta description generation...'},room=str(project_id), namespace='/')
                meta_description = response['choices'][0]['message']['content']

                ##### TEST MODE ONLY #####
                if test_mode != 0:

                    if stop_process.get(project_id, False):
                        stop(project_id)  # Stop process
                        Config.socketio.emit('log', {'data': 'Process stopped by user.'},room=str(project_id), namespace='/')
                        project = db.session.get(Project, project_id)
                        if project:
                            project.in_progress = False
                            db.session.commit()
                        return            

                    # Calculate cost
                    cost = cost_statistics_all(response, app_settings)                

                    ###### Save statistics ###### 
                    task_id = "meta_description"
                    import query
                    query.statistics(db, Statistics, project_id, product_id, app_settings, task_id, response, cost, test_mode=1)

                    ###### SAVE PROCESSED PRODUCT ######
                    url_handle = app_settings['url'] + '/product/' + product_dict['url_handle']
                    title = product_dict['product_name']

                    # Query the Processed_category table for the column token_count for this category
                    record = db.session.query(Processed).filter_by(project_id=project_id, record_id=product_id).first()
                    current_token_count = record.token_count if record else 0

                    if current_token_count is None or current_token_count == 0:
                        token_count = total_tokens_used_product
                        import query

                        #query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, description=description, url_handle=url_handle, title=title)
                    else:
                        token_count = current_token_count + total_tokens_used_product


                    query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, meta_description=meta_description, url_handle=url_handle, token_count=token_count, title=title)
                    total_tokens_used_product = 0
                    ####################################
    
                    ###### Emit the description to the client ######
                    Config.socketio.emit('log', {'data': f'\n{meta_description}\n'},room=str(project_id), namespace='/')

                ##### LIVE MODE #####
                if test_mode == 0:

                    if stop_process.get(project_id, False):
                        stop(project_id)  # Stop process
                        Config.socketio.emit('log', {'data': 'Process stopped by user.'},room=str(project_id), namespace='/')
                        project = db.session.get(Project, project_id)
                        if project:
                            project.in_progress = False
                            db.session.commit()
                        return 

                    # Calculate cost
                    cost = cost_statistics_all(response, app_settings) 
                    
                    ###### Save statistics ######
                    task_id = "meta_description"
                    import query
                    query.statistics(db, Statistics, project_id, product_id, app_settings, task_id, response, cost, test_mode=0)

                    # Update the product description
                    updateProduct(product_id, description, short_description, meta_description, app_settings, project_id)
                    ###### SAVE PROCESSED PRODUCT ######
                    url_handle = app_settings['url'] + '/product/' + product_dict['url_handle']
                    title = product_dict['product_name']

                    # Query the Processed_category table for the column token_count for this category
                    record = db.session.query(Processed).filter_by(project_id=project_id, record_id=product_id).first()
                    current_token_count = record.token_count if record else 0

                    if current_token_count is None or current_token_count == 0:
                        token_count = total_tokens_used_product
                        import query

                        #query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, description=description, url_handle=url_handle, title=title)
                    else:
                        token_count = current_token_count + total_tokens_used_product


                    query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, meta_description=meta_description, url_handle=url_handle, token_count=token_count, published=1, title=title)
                    total_tokens_used_product = 0
                    ####################################
                    Config.socketio.emit('log', {'data': f"{formatted_now}: Product meta description for: {product_dict['product_name']} with ID: {product_dict['product_id']} is updated..."},room=str(project_id), namespace='/')


        ###### EXIT THE LOOP ######
        Config.socketio.emit('log', {'data': f'\nProcess completed...'},room=str(project_id), namespace='/')

    ###############################################
    ########## PROCESS MULTIPLE PRODUCTS ##########
    ###############################################
    else:
        # Global flag to signal stopping the process
        limit_reached = False
        # Build the base URL
        url = f"{app_settings['url']}/api/v2/products"
        # Build the filters based on app_settings
        filters = {}
        if app_settings['only_active']:
            filters['filter[active]'] = 'yes'
        if app_settings['only_category']:
            filters['filter[category_id]'] = app_settings['only_category']
        if app_settings['only_vendor']:
            filters['filter[vendor_id]'] = app_settings['only_vendor']
        if filters:
            url += '?' + urllib.parse.urlencode(filters)
        

        while url and not limit_reached:
            now = datetime.now()
            formatted_now = now.strftime("%d/%m/%Y %H:%M:%S")
            ####### Check if the process has been stopped by the user #######
            if stop_process.get(project_id, False):
                stop(project_id)  # Stop process
                Config.socketio.emit('log', {'data': 'Process stopped by user.'},room=str(project_id), namespace='/')
                project = db.session.get(Project, project_id)
                if project:
                    project.in_progress = False
                    db.session.commit()
                break 

            response = requests.get(url, headers=headers)
            data = response.json()
            if 'data' in data:
                total_products = data['meta']['page']['total']   # get the total number of products
                for product in data['data']:
                    now = datetime.now()
                    formatted_now = now.strftime("%d/%m/%Y %H:%M:%S")
                    all_product_ids.append(product['id'])  # add the product id to the list of all product ids

                    product_count += 1  # increment the counter for each product processed
                    product_id = int(product['id'])
                     # If there is a last processed product and we are on its page, skip the products before it
                    if last_processed_product_id is not None and product_id is not None:
                        if last_processed_product_id >= product_id:
                            continue
                    details = get_product_details(product_id, app_settings)
                    # Skip products with short descriptions
                    if app_settings['skip_products_with_description'] > 0 and len(details['description'].split()) > app_settings['skip_products_with_description']:
                        continue
                    # Build the product dictionary
                    product_dict = {
                        'product_id': product_id,
                        'product_name': details['name'],
                        'url_handle': details['url_handle'],
                        'price_from': details['price_from'],
                        'short_description': details['short_description'],
                        'description': details['description'],
                        'vendor_name': details['vendor_name'],
                        'vendor_slug': details['vendor_slug'],
                        'category_id': details['category_id'],  # add the category id to the product dictionary
                        'category_name': details['category_name'],
                        'category_slug': details['category_slug'],
                        'property_option_values': details['property_option_values']
                    }
                    print(f"{formatted_now}: Processing product with category ID: {product_dict['category_id']}")
                    ############## CHECK IF PRODUCT DESCRIPTION IS ENABLED ##############
                    if enable_product_description:
                        
                        # Create a prompt for each product
                        prompt = create_prompt(product_dict, prompt_settings, app_settings, seo_settings, project_id)
                        if app_settings['print_prompt']:
                            Config.socketio.emit('log', {'data': f"{formatted_now}: \nPrompt message: \n######################################\n{prompt}######################################\n"},room=str(project_id), namespace='/')
                            Config.socketio.emit('log', {'data': f'\nProcess completed...'},room=str(project_id), namespace='/')
                            project = db.session.get(Project, project_id)
                            if project:
                                project.in_progress = False
                                db.session.commit()
                            return(prompt)
                        Config.socketio.emit('log', {'data': f"{formatted_now}: Product description generating: {product_count} out of {total_products}. Product ID: {product_dict['product_id']}"},room=str(project_id), namespace='/')
                        
                        system_prompt = prompt_settings['system_instructions']

                        if system_prompt == "":
                            system_prompt = {"role": "system", "content": "You must add html tags to the text and you must bold important parts and words! Do not use H1 tags, use H2 and H3 tags instead! The links at the text should be accross the entire text not only at the end!"}
                        else:
                            system_prompt = {"role": "system", "content": system_prompt}

                        # Get the response from OpenAI
                        max_retries = 15

                        for attempt in range(max_retries):
                            now = datetime.now()
                            formatted_now = now.strftime("%d/%m/%Y %H:%M:%S")
                            try:
                                response = openai.ChatCompletion.create(
                                    model=app_settings['model'],
                                    messages=[
                                        {"role": "user", "content": prompt},
                                        system_prompt,
                                    ],
                                    temperature=app_settings['temperature'],
                                )
                                total_tokens_used_product += response['usage']['total_tokens']

                                # If the request was successful, break out of the loop
                                break
                            except openai.error.AuthenticationError:
                                # Handle authentication errors (e.g., invalid API key)
                                Config.socketio.emit('log', {'data': 'Authentication Error. Check your OpenAI API Key!'}, room=str(1), namespace='/')
                                break
                            except (openai.error.APIError, openai.error.Timeout, openai.error.ServiceUnavailableError) as e:  
                                #Handle APIError, Timeout, and ServiceUnavailableError for retry
                                wait_time = 2 * (attempt + 1)
                                Config.socketio.emit('log', {'data': f"{formatted_now}: Problem occured at OpenAI. Waiting for {wait_time} seconds before retrying."},room=str(project_id), namespace='/')
                                print(f"Encountered an error: {e.error}. Waiting for {wait_time} seconds before retrying.")
                                time.sleep(wait_time)
                            except Exception as e:
                                # Handle all other exceptions without retrying
                                print(f"An exception occurred: {e}")
                                break
                        else:
                            raise Exception("Maximum number of retries exceeded.")

                        description = response['choices'][0]['message']['content']
                        ##### TEST MODE ONLY #####
                        if test_mode != 0:

                            if stop_process.get(project_id, False):
                                stop(project_id)  # Stop process
                                Config.socketio.emit('log', {'data': 'Process stopped by user.'},room=str(project_id), namespace='/')
                                project = db.session.get(Project, project_id)
                                if project:
                                    project.in_progress = False
                                    db.session.commit()
                                return 
                            
                            # Calculate cost
                            cost = cost_statistics_all(response, app_settings)                

                            ###### Save statistics ###### 
                            task_id = "product_description"
                            import query
                            query.statistics(db, Statistics, project_id, product_id, app_settings, task_id, response, cost, test_mode=1)
                            ###### SAVE PROCESSED PRODUCT ######
                            url_handle = app_settings['url'] + '/product/' + product_dict['url_handle']
                            title = product_dict['product_name']

                            # Query the Processed_category table for the column token_count for this category
                            record = db.session.query(Processed).filter_by(project_id=project_id, record_id=product_id).first()
                            current_token_count = record.token_count if record else 0

                            if current_token_count is None or current_token_count == 0:
                                token_count = total_tokens_used_product
                                import query

                                #query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, description=description, url_handle=url_handle, title=title)
                            else:
                                token_count = current_token_count + total_tokens_used_product

                            
                            query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, description=description, url_handle=url_handle, token_count=token_count, title=title)
                            total_tokens_used_product = 0
                            ####################################
                            ###### Emit the description to the client ######
                            Config.socketio.emit('log', {'data': f'\n{description}\n'},room=str(project_id), namespace='/')
                    
                        ##### LIVE MODE #####
                        if test_mode == 0:

                            if stop_process.get(project_id, False):
                                stop(project_id)  # Stop process
                                Config.socketio.emit('log', {'data': 'Process stopped by user.'},room=str(project_id), namespace='/')
                                project = db.session.get(Project, project_id)
                                if project:
                                    project.in_progress = False
                                    db.session.commit()
                                return 

                            # Calculate cost
                            cost = cost_statistics_all(response, app_settings) 
                            
                            ###### Save statistics ######
                            task_id = "product"
                            import query
                            query.statistics(db, Statistics, project_id, product_id, app_settings, task_id, response, cost, test_mode=0)
                            
                            # Update the product description
                            updateProduct(product_id, description, short_description, meta_description, app_settings, project_id)
                            last_processed_product_id = product_id
                            last_page_url = url
                            ###### SAVE PROCESSED PRODUCT ######
                            url_handle = app_settings['url'] + '/product/' + product_dict['url_handle']
                            title = product_dict['product_name']

                            # Query the Processed_category table for the column token_count for this category
                            record = db.session.query(Processed).filter_by(project_id=project_id, record_id=product_id).first()
                            current_token_count = record.token_count if record else 0

                            if current_token_count is None or current_token_count == 0:
                                token_count = total_tokens_used_product
                                import query

                                #query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, description=description, url_handle=url_handle, title=title)
                            else:
                                token_count = current_token_count + total_tokens_used_product


                            query.save_processed_product(db, Processed, project_id, last_processed_product_id, task_id=task_id, description=description, page_url=last_page_url, url_handle=url_handle, published=1, token_count=token_count, title=title)
                            total_tokens_used_product = 0
                            ####################################
                            Config.socketio.emit('log', {'data': f"{formatted_now}: Updated product description: {product_count} out of {total_products}. Product ID: {product_dict['product_id']}"},room=str(project_id), namespace='/')

                    if enable_product_short_description:
                        response = None
                        prompt = None
                        # Create a prompt for each product
                        prompt = create_prompt_short_description(product_dict, prompt_settings, app_settings, seo_settings, short_description_settings, project_id)
                        if app_settings['print_prompt']:
                            Config.socketio.emit('log', {'data': f"{formatted_now}: \nPrompt message: \n######################################\n{prompt}######################################\n"},room=str(project_id), namespace='/')
                            Config.socketio.emit('log', {'data': f'{formatted_now}: Process completed...'},room=str(project_id), namespace='/')
                            project = db.session.get(Project, project_id)
                            if project:
                                project.in_progress = False
                                db.session.commit()
                            return(prompt)
                        # Create a prompt for each product
                        
                        response = generate_short_description(product_dict, prompt_settings, description, app_settings, seo_settings, short_description_settings, project_id, prompt)
                        Config.socketio.emit('log', {'data': f'{formatted_now}: Short description generation: {product_count} out of {total_products}. Product ID: {product_dict["product_id"]}'},room=str(project_id), namespace='/')
                        short_description = response['choices'][0]['message']['content']
                        ##### TEST MODE ONLY #####
                        if test_mode != 0:
                            if stop_process.get(project_id, False):
                                stop(project_id)  # Stop process
                                Config.socketio.emit('log', {'data': f'{formatted_now}: Process stopped by user.'},room=str(project_id), namespace='/')
                                project = db.session.get(Project, project_id)
                                if project:
                                    project.in_progress = False
                                    db.session.commit()
                                return              

                            # Calculate cost
                            cost = cost_statistics_all(response, app_settings)                

                            ###### Save statistics ###### 
                            task_id = "short_description"
                            import query
                            query.statistics(db, Statistics, project_id, product_id, app_settings, task_id, response, cost, test_mode=1)
                           
                            ###### SAVE PROCESSED PRODUCT ######
                            url_handle = app_settings['url'] + '/product/' + product_dict['url_handle']
                            title = product_dict['product_name']

                            # Query the Processed_category table for the column token_count for this category
                            record = db.session.query(Processed).filter_by(project_id=project_id, record_id=product_id).first()
                            current_token_count = record.token_count if record else 0

                            if current_token_count is None or current_token_count == 0:
                                token_count = total_tokens_used_product
                                import query

                                #query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, description=description, url_handle=url_handle, title=title)
                            else:
                                token_count = current_token_count + total_tokens_used_product


                            query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, short_description=short_description, token_count=token_count, url_handle=url_handle, title=title)
                            total_tokens_used_product = 0
                            ####################################
                           
                            ###### Emit the description to the client ######
                            Config.socketio.emit('log', {'data': f'\n{short_description}\n'},room=str(project_id), namespace='/')
                        
                        ##### LIVE MODE #####
                        if test_mode == 0:

                            if stop_process.get(project_id, False):
                                stop(project_id)  # Stop process
                                Config.socketio.emit('log', {'data': 'Process stopped by user.'},room=str(project_id), namespace='/')
                                project = db.session.get(Project, project_id)
                                if project:
                                    project.in_progress = False
                                    db.session.commit()
                                return 

                            # Calculate cost
                            cost = cost_statistics_all(response, app_settings) 
                            
                            ###### Save statistics ######
                            task_id = "short_description"
                            import query
                            query.statistics(db, Statistics, project_id, product_id, app_settings, task_id, response, cost, test_mode=0)
                            
                            # Update the product description
                            updateProduct(product_id, description, short_description, meta_description, app_settings, project_id)
                            ###### SAVE PROCESSED PRODUCT ######
                            url_handle = app_settings['url'] + '/product/' + product_dict['url_handle']
                            title = product_dict['product_name']
                            # Query the Processed_category table for the column token_count for this category
                            record = db.session.query(Processed).filter_by(project_id=project_id, record_id=product_id).first()
                            current_token_count = record.token_count if record else 0

                            if current_token_count is None or current_token_count == 0:
                                token_count = total_tokens_used_product
                                import query

                                #query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, description=description, url_handle=url_handle, title=title)
                            else:
                                token_count = current_token_count + total_tokens_used_product


                            query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, short_description=short_description, url_handle=url_handle, token_count=token_count, published=1, title=title)
                            total_tokens_used_product = 0
                            ####################################
                            Config.socketio.emit('log', {'data': f"{formatted_now}: Updated short description: {product_count} out of {total_products}. Product ID: {product_dict['product_id']}"},room=str(project_id), namespace='/')

                    ############## CHECK IF META DESCRIPTION IS ENABLED ##############
                    if enable_generate_meta_description:
                        response = None
                        # Create a prompt for each product

                        response = generate_meta_description(product_dict, prompt_settings, app_settings, seo_settings, description, project_id)
                        if app_settings["print_prompt"] is True:
                            project = db.session.get(Project, project_id)
                            if project:
                                project.in_progress = False
                                db.session.commit()
                            return
                        Config.socketio.emit('log', {'data': f'{formatted_now}: Meta description generation: {product_count} out of {total_products}. Product ID: {product_dict["product_id"]}'},room=str(project_id), namespace='/')
                        meta_description = response['choices'][0]['message']['content']

                        ##### TEST MODE ONLY #####
                        if test_mode != 0:

                            if stop_process.get(project_id, False):
                                stop(project_id)  # Stop process
                                Config.socketio.emit('log', {'data': 'Process stopped by user.'},room=str(project_id), namespace='/')
                                project = db.session.get(Project, project_id)
                                if project:
                                    project.in_progress = False
                                    db.session.commit()
                                return             

                            # Calculate cost
                            cost = cost_statistics_all(response, app_settings)                

                            ###### Save statistics ###### 
                            task_id = "meta_description"
                            import query
                            query.statistics(db, Statistics, project_id, product_id, app_settings, task_id, response, cost, test_mode=1)

                            ###### SAVE PROCESSED PRODUCT ######
                            url_handle = app_settings['url'] + '/product/' + product_dict['url_handle']
                            title = product_dict['product_name']

                            # Query the Processed_category table for the column token_count for this category
                            record = db.session.query(Processed).filter_by(project_id=project_id, record_id=product_id).first()
                            current_token_count = record.token_count if record else 0

                            if current_token_count is None or current_token_count == 0:
                                token_count = total_tokens_used_product
                                import query

                                #query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, description=description, url_handle=url_handle, title=title)
                            else:
                                token_count = current_token_count + total_tokens_used_product


                            query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, meta_description=meta_description, token_count=token_count, url_handle=url_handle, title=title)
                            total_tokens_used_product = 0
                            ####################################

                            ###### Emit the description to the client ######
                            Config.socketio.emit('log', {'data': f'\n{meta_description}\n'},room=str(project_id), namespace='/')

                        ##### LIVE MODE #####
                        if test_mode == 0:

                            if stop_process.get(project_id, False):
                                stop(project_id)  # Stop process
                                Config.socketio.emit('log', {'data': 'Process stopped by user.'},room=str(project_id), namespace='/')
                                project = db.session.get(Project, project_id)
                                if project:
                                    project.in_progress = False
                                    db.session.commit()
                                return 

                            # Calculate cost
                            cost = cost_statistics_all(response, app_settings) 
                            
                            ###### Save statistics ######
                            task_id = "meta_description"
                            import query
                            query.statistics(db, Statistics, project_id, product_id, app_settings, task_id, response, cost, test_mode=0)

                            # Update the product description
                            updateProduct(product_id, description, short_description, meta_description, app_settings, project_id)
                            ###### SAVE PROCESSED PRODUCT ######
                            url_handle = app_settings['url'] + '/product/' + product_dict['url_handle']
                            title = product_dict['product_name']

                            # Query the Processed_category table for the column token_count for this category
                            record = db.session.query(Processed).filter_by(project_id=project_id, record_id=product_id).first()
                            current_token_count = record.token_count if record else 0

                            if current_token_count is None or current_token_count == 0:
                                token_count = total_tokens_used_product
                                import query

                                #query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, description=description, url_handle=url_handle, title=title)
                            else:
                                token_count = current_token_count + total_tokens_used_product


                            query.save_processed_product(db, Processed, project_id, product_id, task_id=task_id, meta_description=meta_description, url_handle=url_handle, token_count=token_count, published=1, title=title)
                            total_tokens_used_product = 0
                            ####################################
                            Config.socketio.emit('log', {'data': f"{formatted_now}: Updated meta description:  with ID: {product_count} out of #{total_products}. Product ID: {product_dict['product_id']}"},room=str(project_id), namespace='/')

                    # Check if test mode is enabled and if the product count has reached the limit
                    if test_mode > 0:
                        Config.socketio.emit('log', {'data': f'{formatted_now}: Test mode completed...'},room=str(project_id), namespace='/')
                        limit_reached = True
                        project = db.session.get(Project, project_id)
                        if project:
                            project.in_progress = False
                            db.session.commit()
                        return
            ###### NEXT PAGE ######
            url = data['links']['next'] if 'next' in data['links'] else None
    
    Config.socketio.emit('log', {'data': f'\n{formatted_now}: Completed...'},room=str(project_id), namespace='/')
    project = db.session.get(Project, project_id)
    if project:
        project.in_progress = False
        db.session.commit()
    return(200)

def stop(project_id):
    print(f'Stopping the process for project {project_id}...')
    stop_process[project_id] = True     
        
def get_last_processed_product(db, Processed, project_id):
    try:
        last_product = db.session.query(Processed).filter(Processed.project_id == project_id).filter(Processed.task_id == "product").order_by(desc(Processed.record_id)).first()
        if last_product:
            return last_product.record_id, last_product.page_url
        else:
            return None, None
    except Exception as e:
        print(f"Error: {str(e)}")
        return None, None

    

def calculate_all(app_settings, project_id):
    now = datetime.now()
    formatted_now = now.strftime("%d/%m/%Y %H:%M:%S")
    gpt3_price = 0.0035 / 1000
    gpt4_price = 0.09 / 1000
    tokens_per_word = 4.33  # approx conversion from words to tokens
    seo_package_multiplier = 1.57
    cloudcart_price_multiplier_gpt_3_5 = 99
    cloudcart_price_multiplier_gpt_4 = 7

    # Determine the price per token
    if app_settings['model'] == 'gpt-3.5-turbo':
        price_per_token = gpt3_price * cloudcart_price_multiplier_gpt_3_5
    else:
        price_per_token = gpt4_price * cloudcart_price_multiplier_gpt_4

    # Determine the price per token
    if app_settings['model'] == 'gpt-3.5-turbo':
        price_per_token_cost = gpt3_price
    else:
        price_per_token_cost = gpt4_price
        

    # Get the total tokens from the response
    getTotalProducts = getProducts(app_settings, project_id)

    # Convert length in words to tokens
    length_in_tokens = app_settings['length'] * tokens_per_word

    # Calculate cost
    if app_settings['use_seo_package']:
        cost = (((getTotalProducts * length_in_tokens) * seo_package_multiplier) * price_per_token)
        cost_cc = (((getTotalProducts * length_in_tokens)) * price_per_token_cost)
    else:
        cost = ((getTotalProducts * length_in_tokens) * price_per_token)
        cost_cc = ((getTotalProducts * length_in_tokens) * price_per_token_cost)

    formatted_cost = f"{0.92 * cost:.2f}"   # format cost as a float with 3 decimal places

    Config.socketio.emit('log', {'data': f"{formatted_now}: Approximate estimated cost for model {app_settings['model']} for {getTotalProducts} products with description of {app_settings['length']} words each: €{formatted_cost} EUR without VAT"},room=str(project_id), namespace='/')

    return formatted_cost


def getProducts(app_settings, project_id):
    headers = {
        'X-CloudCart-ApiKey': app_settings['X-CloudCart-ApiKey'],
    }

    # Build the base URL
    url = f"{app_settings['url']}/api/v2/products"

    if not validators.url(url):
        raise Exception("The URL provided in 'app_settings' is not valid")
       
    # Build the filters based on app_settings
    filters = {}
    if app_settings['only_active']:
        filters['filter[active]'] = 'yes'
    if app_settings['only_category']:
        filters['filter[category_id]'] = app_settings['only_category']
    if app_settings['only_vendor']:
        filters['filter[vendor_id]'] = app_settings['only_vendor']

    # Add the filters to the URL
    if filters:
        url += '?' + urllib.parse.urlencode(filters)
    
    max_retries = 15

    for attempt in range(max_retries):
        now = datetime.now()
        formatted_now = now.strftime("%d/%m/%Y %H:%M:%S")
        try:
            response = requests.get(url, headers=headers)
            if response.status_code in (429, 500, 502, 503):  # Retry for status codes 429, 500, 502, and 503
                raise Exception(f"Request to {url} failed with status code {response.status_code}. The response was: {response.text}")
            elif response.status_code != 200:  # For other non-200 status codes, fail immediately
                raise Exception(f"Request to {url} failed with status code {response.status_code}. The response was: {response.text}")
            
            data = response.json()
            total_products = data['meta']['page']['total']
            return total_products  # If request was successful, break out of the loop and return the total_products
        except Exception as e:
            if attempt < max_retries - 1:  # If it's not the last attempt, wait and then continue to the next iteration
                wait_time = 5 * (attempt + 1)
                Config.socketio.emit('log', {'data': f"{formatted_now}: Error occured at CloudCart. Waiting for {wait_time} seconds before retrying."},room=str(project_id), namespace='/')
                time.sleep(wait_time)
            else:  # On the last attempt, fail with an exception
                raise




def getCategories(app_settings):
    headers = {
        'X-CloudCart-ApiKey': app_settings['X-CloudCart-ApiKey'],
    }

    # Build the base URL
    url = f"{app_settings['url']}/api/v2/categories"

    if not validators.url(url):
        print(url)
        raise Exception("The URL provided in 'app_settings' is not valid")
    
    categories = []
    max_retries = 15

    while url:
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers)
                if response.status_code != 200:
                    raise Exception(f"Request to {url} failed with status code {response.status_code}. The response was: {response.text}")

                data = response.json()
                
                # Add the data from this page to our list of categories
                categories.extend(data['data'])

                # Get the next page URL, if it exists
                url = None
                if "next" in data["links"]:
                    url = data["links"]["next"]

                # If request was successful, break out of the loop
                break

            except Exception as e:
                if attempt < max_retries - 1:  # If it's not the last attempt, wait and then continue to the next iteration
                    wait_time = 5 * (attempt + 1)
                    print(f"Error occured at CloudCart. Waiting for {wait_time} seconds before retrying.")
                    time.sleep(wait_time)
                else:  # On the last attempt, fail with an exception
                    raise

    return categories


def getVendors(app_settings):
    headers = {
        'X-CloudCart-ApiKey': app_settings['X-CloudCart-ApiKey'],
    }

    # Build the base URL
    url = f"{app_settings['url']}/api/v2/vendors"

    if not validators.url(url):
        raise Exception("The URL provided in 'app_settings' is not valid")
    
    vendors = []
    max_retries = 15

    while url:
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers)
                if response.status_code != 200:
                    raise Exception(f"Request to {url} failed with status code {response.status_code}. The response was: {response.text}")

                data = response.json()
                
                # Add the data from this page to our list of vendors
                vendors.extend(data['data'])
        
                # Get the next page URL, if it exists
                url = None
                if "next" in data["links"]:
                    url = data["links"]["next"]

                # If request was successful, break out of the loop
                break

            except Exception as e:
                if attempt < max_retries - 1:  # If it's not the last attempt, wait and then continue to the next iteration
                    wait_time = 5 * (attempt + 1)
                    print(f"Error occured at CloudCart. Waiting for {wait_time} seconds before retrying.")
                    time.sleep(wait_time)
                else:  # On the last attempt, fail with an exception
                    raise

    return vendors


def cost_statistics_all(response, app_settings):

    tokens_per_word = 4.33  # approx conversion from words to tokens
    seo_package_multiplier = 1.57
    cloudcart_price_multiplier_gpt_3_5 = 99
    cloudcart_price_multiplier_gpt_4 = 7

    gpt3_completion_price = 0.0035 / 1000
    gpt4_completion_price = 0.09 / 1000


    # Get the total tokens from the response
    total_tokens = response['usage']['total_tokens']

    # Determine the price per token
    if app_settings['model'] == 'gpt-3.5-turbo':
        price_per_token = gpt3_completion_price * cloudcart_price_multiplier_gpt_3_5
    else:
        price_per_token = gpt4_completion_price * cloudcart_price_multiplier_gpt_4


    # Calculate cost
    if app_settings['use_seo_package']:
        cost = total_tokens * seo_package_multiplier * price_per_token
    else:
        cost = total_tokens * price_per_token

    return cost

def calculate_cost(response, app_settings):
    gpt3_completion_price = 0.000002
    gpt3_input_price = 0.0000015
    gpt4_completion_price = 0.00006
    gpt4_input_price = 0.00003


    # Get the total tokens from the response
    input_tokens = response['usage']['prompt_tokens']
    output_tokens = response['usage']['completion_tokens']
    total_tokens = response['usage']['total_tokens']

    # Calculate cost
    if app_settings['model'] == 'gpt-3.5-turbo':
        cost = (input_tokens * gpt3_input_price) + (output_tokens * gpt3_completion_price)
    else:
        cost = (input_tokens * gpt4_input_price) + (output_tokens * gpt4_completion_price)

    return cost

def write_to_csv(file_name, row):
    with open(file_name, 'a', newline='') as csvfile:  # Open the file in append mode
        fieldnames = ['url', 'total_cost']  # The column headers
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writerow(row)


### TO DO - ABORT PROCESS
