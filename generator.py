import requests
import re
import openai
from urllib.parse import urlparse
import csv
import json
import os
from flask_socketio import SocketIO, emit
import validators


socketio = None

def set_socketio(sio):
    global socketio
    socketio = sio

# Initialize the settings as empty dictionaries
app_settings = {}
seo_settings = {}
prompt_settings = {}
  

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

def updateProduct(product_id, description, app_settings):
    headers = {
        'X-CloudCart-ApiKey': app_settings['X-CloudCart-ApiKey'],
        'Content-Type': 'application/vnd.api+json',
    }
    url = f"{app_settings['url']}/api/v2/products/{product_id}"

    body = {
        "data": {
            "type": "products",
            "id": str(product_id),
            "attributes": {
                "description": description
            }
        }
    }

    response = requests.patch(url, data=json.dumps(body), headers=headers)
    if response.status_code != 200:
        raise Exception(f"Request to {url} failed with status code {response.status_code}. The response was: {response.text}")
    
    return response.json()

def get_keywords(seo_settings, app_settings, product):
    if seo_settings['use_keywords'] == 0:
        return ''
    prompt = f'You are skilled SEO expert. Research ONLY the top {seo_settings["use_keywords"]} long-tail keywords, from the title of this product in {app_settings["language"]} language. Use the category \"{product["category_name"]}\" and the brand \"{product["vendor_name"]}\" only if you are absolutly sure that the information is critical for the top long-tail keyword. Please note that I want only the words without any other explanations from your side! Return the keywords by comma separated.\n'

    response = openai.ChatCompletion.create(
        model=app_settings['model'],
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0,
    )

    # Do something with the response, e.g., print the message content
    return(response['choices'][0]['message']['content'])



def create_prompt(product, prompt_settings, app_settings, seo_settings):
    # Initialize an empty string for the prompt
    prompt = ''
    # Check if SEO package is in use
    if app_settings['use_seo_package']:
        # Create an anchor tag with product name and URL
        if seo_settings['link_to_product']:
            product_name_link = f'<a href="{app_settings["url"]}/product/{product["url_handle"]}" target="_blank" alt="rewrite in {app_settings["language"]} language the alt title: \"{product["product_name"]}\"">put the product title here</a>'
        if seo_settings['link_to_category']:
            category_name_link = f'<a href="{app_settings["url"]}/category/{product["category_slug"]}" target="_blank" alt="rewrite in {app_settings["language"]} language, the alt title: \"{product["category_name"]}\"">put the category name here</a>'
        if seo_settings['link_to_vendor']:
            vendor_name_link = f'<a href="{app_settings["url"]}/vendor/{product["vendor_slug"]}" target="_blank" alt="{product["vendor_name"]}">put the vendor name here</a>'
        if seo_settings['link_to_more_from_same_vendor_and_category']:
            more_from_same_vendor_and_category_link = f'<a href="{app_settings["url"]}/category/{product["category_slug"]}?vendors={product["vendor_slug"]}" target="_blank" alt="rewrite in {app_settings["language"]} language the alt title: \"{product["vendor_name"]} - {product["category_name"]}\"">give the user the option to see more from \"{product["vendor_name"]}\"</a>'
        if seo_settings['use_keywords'] != 0:
            keywords = get_keywords(seo_settings, app_settings, product)
        if seo_settings['link_keyword_to_product']:
            keyword_product_link = f'<a href="{app_settings["url"]}/product/{product["url_handle"]}" target="_blank" alt="rewrite in {app_settings["language"]} language the alt title: \"{product["product_name"]}\""> put the keywords here </a>'

    # Main instructions
    prompt += f'Strictly follow the instructions step by step! \nMain instructions: \n'
    prompt += f"You are {app_settings['niche']} and {prompt_settings['purpouse']} copywriter at {app_settings['website_name']}. This product description is published online at \"{app_settings['website_name']}\" (do not invite the user to go to the store, he is already there!). You are writing and adapting the entire text in {app_settings['language']} language. \n"
    prompt += f"The product description must be in no more than {app_settings['length']} words and its purpouse is for \"{prompt_settings['purpouse']}\".\n"

    # SEO and Keywords instructions
    if app_settings['use_seo_package']:
        prompt += f"This part is highly important! Stryctly follow the SEO and keywords instructions: \n"
        if seo_settings['use_keywords'] != 0:
            prompt += f"All keywords should be used in the most natural way accros the generated description. For example at the beginning of the text, at the middle and at the end. The description should contains the following keywords: {keywords}. Use each combination not less than {seo_settings['keywords_density']} times. \n"
        if seo_settings['use_free_keywords'] != '':
            free_keywords = f'and you must combine it with the best relevant keywords from here: \"{seo_settings["use_free_keywords"]}\"'
            prompt += f'You are skilled SEO expert. Research ONLY the top {seo_settings["use_keywords"]} long-tail keywords, from the title of this product {free_keywords} in {app_settings["language"]} language. Use the category \"{product["category_name"]}\" and the brand \"{product["vendor_name"]}\" only if you are absolutly sure that the information is critical for the top long-tail keyword. Please note that I want only the words without any other explanations from your side! Return the keywords by comma separated. \n'
        if seo_settings['link_keyword_to_product']:
            prompt += f"In addition, you must make at least {seo_settings['link_keyword_density']} links to that keywords with this link: {keyword_product_link}. \n"
        if seo_settings['link_to_product']:
            prompt += f"add this link to one of the product titles: {product_name_link}, "
        if seo_settings['link_to_category']:
            prompt += f"add this link to one of the category names: {category_name_link}, "
        if seo_settings['link_to_vendor']:
            prompt += f"Add this link to one of the vendor names: {vendor_name_link}, "
        if seo_settings['link_to_more_from_same_vendor_and_category']:
            prompt += f"Add a link to find more products from category: {product['category_name']} and brand: {product['vendor_name']}: {more_from_same_vendor_and_category_link}. \n"

    # Product information instructions
    prompt += f"\n Product information instructions: \n"
    prompt += f"1. The store is \"{app_settings['website_name']}\";\n"
    if prompt_settings['product_name']:
        prompt += f"2. Rewrite the title in SEO way. Remove irrelevants from \"{product['product_name']}\"; \n"
    # Check if 'price_from' is in prompt_settings and is not None
    if prompt_settings.get('price_from'):
        # Check if 'show_price' is in prompt_settings and is True
        if prompt_settings.get('show_price'):
            # Check if 'price_from' and 'currency' exist in the product and app_settings respectively
            if product.get('price_from') and app_settings.get('currency'):
                prompt += f"3. The product price is {product['price_from']} {app_settings['currency']} ;\n"
            else:
                prompt += "3. Do not mention the product price but if you decide you can use some words about the benefit of the price;\n"
                
        # Check if 'price_from' is in the product and 'free_delivery_over' is in app_settings and both are not None
        if product.get('price_from') and app_settings.get('free_delivery_over') and \
        float(product['price_from']) > app_settings['free_delivery_over']:
            # Check if 'mention_free_delivery_price' is in app_settings and is True
            if app_settings.get('mention_free_delivery_price'):
                # Check if 'currency' is in app_settings and is not None
                if app_settings.get('currency'):
                    prompt += f"4. This product might be eligible for free delivery for orders over {app_settings['free_delivery_over']} {app_settings['currency']} but advice the customer to check it when they are purchasing;\n"
            else:
                prompt += "4. This product might be eligible for free delivery but advice the customer to check it when they are purchasing.\n"

    # Product specifications instructions
    if prompt_settings['short_description']:
        prompt += f"4. Use this short description for your product description: \"{product['short_description']}\";\n"
    if prompt_settings['description']:
        prompt += f"5. Use the existing description for your product description: \"{product['description']}\"\n"
    if prompt_settings['vendor_name']:
        prompt += f"6. Te brand of the product is: \"{product['vendor_name']}\";\n"
    if prompt_settings['category_name']:
        prompt += f"7. Category is: \"{product['category_name']}\" (you must use it only for reference for the description but not directly);\n"
    if prompt_settings['property_option_values']:
        prompt += f"8. Use product characteristics: \"{product['property_option_values']}\". You must write feature/benefit dichotomy description. For example, stating that a dishwasher applies high heat and water pressure (or worse, providing numbers with no context) doesn't tell the reader anything. These are features, and they resonate with the reader much better when you pair them with their benefit. In this case, the benefit might be that buying this dishwasher will liberate them from having to remove food residue and stains by hand;\n"
    if app_settings['use_seo_package']:
        prompt += f"9. Avoid superfluous words. Avoid Generic Writing, instead, employ Unique features and benefits, The 'What' of what your product can do for them, Explanation of the specific ways the product will improve their lives. Don't use the passive voice.\n"
    
    return prompt


def get_all_products(app_settings):

    headers = {
        'X-CloudCart-ApiKey': app_settings['X-CloudCart-ApiKey'],
    }

    processed_products = []
    socketio.emit('log', {'data': f'Started...'}, namespace='/')
    # Create 'data' directory if it doesn't exist
    if not os.path.exists('data'):
        os.makedirs('data')
    
    # Build the base URL
    url = f"{app_settings['url']}/api/v2/products"

    if not validators.url(url):
        raise Exception("The URL provided in 'app_settings' is not valid")



    # Construct filename from URL without http:// or https://
    parsed_url = urlparse(app_settings['url'])
    url_without_http = parsed_url.netloc
    filename = f"data/{url_without_http}.csv"

    # Check if file exists, if not create it
    if not os.path.isfile(filename):
        with open(filename, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Product ID", "Generated description"])

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

    # Add the filters to the URL
    if filters:
        url += '?' + urllib.parse.urlencode(filters)

    # Set the OpenAI key
    openai.api_key = app_settings['openai_key']

    total_tokens_all_products = 0
    total_cost_all_products = 0
    product_count = 0  # add a counter for products processed
    test_mode = app_settings['test_mode']  # Get the test mode value from settings
    description = ''  # Initialize the description variable
    if test_mode > 0:
        # Get current total cost
        total_csv_file = f"data/total_costs_test_mode.csv"
        if not os.path.isfile(total_csv_file):
            with open(total_csv_file, 'w') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=['url', 'total_cost'])
                writer.writeheader()
        current_row = read_from_csv(total_csv_file, app_settings['url'])
        current_total_cost = float(current_row['total_cost']) if current_row is not None else 0
        if current_total_cost > 1:
            socketio.emit('log', {'data': f'The limit for {app_settings["url"]} has been reached.'}, namespace='/')
            return

    while url:
        response = requests.get(url, headers=headers)
        data = response.json()

        if 'data' in data:
            total_products = data['meta']['page']['total']   # get the total number of products
            for product in data['data']:

                product_count += 1  # increment the counter for each product processed
                product_id = product['id']

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
                    'category_name': details['category_name'],
                    'category_slug': details['category_slug'],
                    'property_option_values': details['property_option_values']
                }
                
                
                # Create a prompt for each product
                prompt = create_prompt(product_dict, prompt_settings, app_settings, seo_settings)
                if app_settings['print_prompt']:
                    socketio.emit('log', {'data': f"\nPrompt message: \n######################################\n{prompt}######################################\n"}, namespace='/')
                
                    return(prompt)
                socketio.emit('log', {'data': f"Processing product {product_count} of {total_products} with name: {product_dict['product_name']} and ID: {product_dict['product_id']}"}, namespace='/')
                # Get the response from OpenAI
                response = openai.ChatCompletion.create(
                    model=app_settings['model'],
                    messages=[
                        {"role": "user", "content": prompt},
                        {"role": "system", "content": "You must add html tags to the text and you must bold important parts and words! Do not use H1 tags, use H2 and H3 tags instead! The links at the text should be accross the entire text not only at the end!"},
                    ],
                    temperature=app_settings['temperature'],
                )

                description = response['choices'][0]['message']['content']

                # Write generated descriptions to a CSV log
                with open(filename, 'a', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow([product_id, description])


                ##### TEST MODE ONLY #####
                if test_mode != 0:

                    
                    if not os.path.isfile(total_csv_file):
                        with open(total_csv_file, 'w') as csvfile:
                            writer = csv.DictWriter(csvfile, fieldnames=['url', 'total_cost'])
                            writer.writeheader()
                        
                    # Get current total cost
                    current_row = read_from_csv(total_csv_file, app_settings['url'])
                    current_total_cost = float(current_row['total_cost']) if current_row is not None else 0
                    if current_total_cost > 1:
                        socketio.emit('log', {'data': f'The limit for {app_settings["url"]} has been reached.'}, namespace='/')
                        return

                    # Calculate cost
                    cost = calculate_cost(response, app_settings)                

                    # Add to running totals
                    total_tokens_all_products += response['usage']['total_tokens']
                    total_cost_all_products += cost

                    # Print the generated description and the cost details
                    print(description)
                    print('------------------------------------------------------------------')
                    print('Total input tokens: ', response['usage']['prompt_tokens'])
                    print('Total output tokens: ', response['usage']['completion_tokens'])
                    print('Total tokens for this product: ', response['usage']['total_tokens'])
                    print('Running total tokens for all products: ', total_tokens_all_products)
                    print('Running total cost for all products: ', total_cost_all_products)
                    print('------------------------------------------------------------------')
                    print('#############################################')

                    # Update the CSV with the cost information
                    current_row = read_from_csv(total_csv_file, app_settings['url'])
                    if current_row is None:
                        # If this URL hasn't been recorded yet, create a new row
                        write_to_csv(total_csv_file, {'url': app_settings['url'], 'total_cost': total_cost_all_products})
                    else:
                        # If it has, update the total cost
                        existing_total_cost = float(current_row['total_cost'])
                        new_total_cost = existing_total_cost + total_cost_all_products
                        update_csv(total_csv_file, app_settings['url'], new_total_cost)

                    # Preview the description
                    socketio.emit('log', {'data': f'\n{description}\n'}, namespace='/')
                
                # Check if test mode is enabled and if the product count has reached the limit
                if test_mode > 0 and product_count >= test_mode:
                    break
                
                if test_mode == 0:
                    ###### LOGS AND CALCULATIONS ######

                    # Calculate the number of tokens
                    csv_file_total = 'data/total_costs.csv'
                    if not os.path.isfile(csv_file_total):
                        with open(csv_file_total, 'w') as csvfile:
                            writer = csv.DictWriter(csvfile, fieldnames=['url', 'total_cost'])
                            writer.writeheader()

                    # Get current total cost
                    current_row = read_from_csv(csv_file_total, app_settings['url'])
                    current_total_cost = float(current_row['total_cost']) if current_row is not None else 0

                    # Calculate cost
                    cost = calculate_cost(response, app_settings)                

                    # Add to running totals
                    total_tokens_all_products += response['usage']['total_tokens']
                    total_cost_all_products += cost

                    # Update the CSV with the cost information
                    current_row = read_from_csv(csv_file_total, app_settings['url'])
                    if current_row is None:
                        # If this URL hasn't been recorded yet, create a new row
                        write_to_csv(csv_file_total, {'url': app_settings['url'], 'total_cost': total_cost_all_products})
                    else:
                        # If it has, update the total cost
                        existing_total_cost = float(current_row['total_cost'])
                        new_total_cost = existing_total_cost + total_cost_all_products
                        update_csv(csv_file_total, app_settings['url'], new_total_cost)
                    
                    # Update the product description
                    updateProduct(product_id, description, app_settings)
                    socketio.emit('log', {'data': f"Product: {product_dict['product_name']} with ID: {product_dict['product_id']} is updated..."}, namespace='/')
            socketio.emit('log', {'data': f'\nProcess completed...'}, namespace='/')
            return description 
        
    
        url = data['links']['next'] if 'next' in data['links'] else None

        

def calculate_all(app_settings):
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
    getTotalProducts = getProducts(app_settings)

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

    socketio.emit('log', {'data': f"Approximate estimated cost for {getTotalProducts} products: €{formatted_cost} EUR without VAT || CC = {cost_cc}"}, namespace='/')

    return formatted_cost


def getProducts(app_settings):
    headers = {
        'X-CloudCart-ApiKey': app_settings['X-CloudCart-ApiKey'],
    }

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

    # Add the filters to the URL
    if filters:
        url += '?' + urllib.parse.urlencode(filters)
 


    response = requests.get(url, headers=headers)
    data = response.json()
    total_products = data['meta']['page']['total']

    return total_products


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

def read_from_csv(file_name, url):
    with open(file_name, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row['url'] == url:
                return row
    return None

def update_csv(file_name, url, total_cost):
    # Read all rows
    rows = []
    with open(file_name, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        rows = list(reader)

    # Update the row with the matching URL
    for row in rows:
        if row['url'] == url:
            row['total_cost'] = total_cost

    # Write all rows back to the file
    with open(file_name, 'w', newline='') as csvfile:
        fieldnames = ['url', 'total_cost']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

### TO DO - ABORT PROCESS
