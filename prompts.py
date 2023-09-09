from helpers import *

####### CATEGORY PROMPTS #######

def generate_default_prompts(app_settings, seo_settings, target_category_name, unique_keywords_string):
    """
    Generate the default prompts based on the seo_settings.
    """
    prompt = (f"You are an SEO expert and Copywriter writing in {app_settings['language']} at {app_settings['url']} online store. The title of the store is: {app_settings['website_name']}. "
              f"with a focus on depth, user experience, keyword optimization (including stemming), engagement, and a minimum length of {app_settings['length']} words, ensuring uniqueness.\n")
    #prompt += ("Imagine you're having a relaxed conversation with a close friend, and you're introducing them to this category for the first time."
    #           "Use 'I', 'we', and 'you' to make it personal and engaging. How would you draw parallels from everyday life to explain the essence of this category?"
    #           "Think of a rhetorical question that could pique their interest. Can you craft an analogy or metaphor that paints a vivid picture of this category's uniqueness?"
    #           "Remember, it's not just about informing; it's about connecting and resonating."
    #           "Make sure your content flows seamlessly and is formatted clearly with headers, bullet points, or numbered lists where appropriate.\n")
    if app_settings['use_seo_package'] and seo_settings["generic_keywords"]:
        prompt += f"As an SEO expert with a focus on keyword stemming, you must derive and choose the most appropriate stemmed variations from the keywords provided in this list: {unique_keywords_string}. Understand the core meaning and concept of each keyword, and then incorporate these stemmed variations intuitively and naturally across the entire text.\n"
    return prompt

def generate_default_prompts_end(app_settings, seo_settings):
    """
    Generate the default prompts for the end.
    """
    prompt = f"DO NOT ADD OR REFFER TO ANY WORDS OF THE THIS PROMPT! THE CONTENT SHOULD BE MINIMUM OF {app_settings['length']} WORDS! ALL OF THE INFORMATION IS FOR BUILDING THE PERFECT CATEGORY DESCRIPTION!\n"

    return prompt

def compile_intro_prompt(app_settings, category_settings, seo_settings, target_category_name, target_category_url, unique_keywords_string):
    """
    Generate content for the first section based on the information and prompts provided.
    """

    #Unique keywords string
    print(f"UNIQUE KEYWORDS STRING {unique_keywords_string}")

    

    translated_category_name = google_translate(f"{target_category_name}", "en")

    if app_settings['use_seo_package'] and seo_settings['wiki_links']:
        
        query = f"{translated_category_name} wikipedia"
        
        wikilink = google_custom_search(query)
        print(f"Wikilink {wikilink}")
        
        if is_valid_url(wikilink):  # Validate the URL
            wikipedia_link = f'<a href="{wikilink}">{target_category_name}</a>'
        else:
            wikipedia_link = target_category_name  # Use plain text if the URL is not valid

    prompt = generate_default_prompts(app_settings, seo_settings, target_category_name, unique_keywords_string)

    if app_settings['use_seo_package'] and seo_settings["include_category_name_at_headings"]:
        if app_settings['use_seo_package'] and seo_settings['cat_links']:
            prompt += "Heading:\n"
            prompt += f"Craft an SEO optimized heading for the category {target_category_name} and add this link: {target_category_url}. Be creative to craft this marketing ready heading. If it is possible include and the best appropriate keyword into the link. Make it H2 html tag and keep the link.\n"
            prompt += "Example: If the category is for sandals the heading could be: \"The best <a href=\"target_category_url\" target=\"_blank\">sandals for women</a>. Embrace Every Step with Style and Comfort!\".\n"

        else:
            prompt += "Heading:\n"
            prompt += f"Craft a creative, marketing and SEO optimized heading for the category {target_category_name}. Make it into H2 html tag.\n"
            print(f"ONLY NAME OF THE CATEGORY")
    else:
        prompt += "Heading:\n"
        prompt += f"Craft an Marketing ready heading for a category. Make the heading with a context {target_category_name}. Make it into H2 html tag.\n"
        prompt += "Example: If the category is for sandals the heading could be: \"The best sandals for women. Embrace Every Step with Style and Comfort!\".\n"
        print(f"WITHOUT NAME OF THE CATEGORY")

    prompt += f"Craft general statement about the importance or ubiquity of the product category {target_category_name}. Describe the common purposes or benefits of owning such products. At the end do not conclude or summerize! Just stop!\n"
    if category_settings['number_images']:

        #### IMAGE SEARCH KEYWORD DEFINITION ####
        # check if unique_keywords_string is empty
        if unique_keywords_string:
            target_prompt = f"Use the following keywords from this list {unique_keywords_string} and craft a keyword that will be used to search for images. It is highly important the keyword should be broad but in close relation with the topic '{target_category_name}'. Return only the keyword and nothing more. Translate the keyword in English.\n"
        else:
            target_prompt = f"Craft a keyword that will be used to search for images. It is highly important the keyword should be broad but in close relation with the topic '{target_category_name}'. Return only the keyword and nothing more. Translate the keyword in English.\n"
        target_system_prompt = "You are English researcher. Return only the word in english and nothing more\n"
        target_keyword = openai_generic(app_settings, target_prompt, target_system_prompt)
        print(f"TARGET KEYWORD {target_keyword}")
        image_urls = get_unsplash_image(category_settings, query=target_keyword)
        prompt += (f"Use the following images accross the entire description {image_urls}. They will illustrate important text sections/blocks:\n")
        prompt += (f"Example of the HTML structure for each of the images :\n"
           "<div style=\"display: flex; justify-content: center; align-items: center; flex-wrap: wrap;\">"
           "<img src=\"IMAGE_URL\" alt=\"PRODUCT_NAME or something related no longer than 60 characters\" width=\"400px\">"
           "<p style=\"padding-left: 25px;\" class=\"col-sm-10 col-md-9 col-lg-6\">"
           f"Here comes your sections/blocks that you want to illustrate with an image</p></div>"
           "You can change the image possition for the next text block at right or left. Example:\n"
           "If you wish your image to be at the left that the img src should be befor the p element. If you want to be at the right the p element should be befor the img src.\n"
           )
        #prompt += (f"Use the following images accross the entire description. They will illustrate important text sections/blocks: {image_urls}. It is mendatory to use HTML tag \"img src\" to add the images. It is a must and important to wrap the image with a text section starting from its heading and give padding at least 25px between the text and the image. To wrap the image with the text section starting from its heading you should use two html elemts. One element could be div with display: flex and the second element is the img src. This is an example of the structure if the image is at the left: <div style=\"display: flex; align-items: center;\">first is the image <img src> and second is the <p style=\"add at least 25px padding from the image and text\">the text</p></div>. If the image is at the right the text have to be first and after it the image. You have to choose the orientation of each image. Most appropriate parts are the begginings of new sections including the heading.\n")
    
    if app_settings['use_seo_faq_package'] and seo_settings["e_e_a_t"]:
        prompt += ("Knowing the E-E-A-T standard, craft the entire product description by following Google guidelines:\n"
                    "Does the content demonstrate first-hand experience?\nDoes the content demonstrate in-the-field experience?\n"
                    "How well does the content share a personal experience, perspective, or feelings on a topic?\n"
                    "Does content also demonstrate that it was produced with some degree of experience, such as actual product use, or communicating what a person experienced?\n"
                    "How original is the content?\nDoes this content demonstrate a depth of expertise in this topic?\n"
                    "The goals:\n1. Experience: goal minimum 9.\n2. Effort: goal minimum 9.\n3. Quality: no less than 10.\n4. Uniqueness: 8.\n5. Depth: 9.\nThe overall score must be no more than 9 out of 10!!!\n")
    prompt += "You are working on Introduction part of the entire category description. Do NOT conclude or summarize it! Below are eventually other parts such as: Highlight of the Top brands and Best selling/quality product, etc.\n"
    
    if category_settings['interesting_fact']:
        prompt += f"Craft an interesting fact based on the description that will add value to the product. It could be a fact about the product, the category, or the industry. It could be a statistic, a quote, or a fun fact. Make sure that it is relevant to the category {target_category_name}.\n"

    
    if app_settings['use_seo_package'] and seo_settings["generic_keywords"]:
        prompt += f"As an SEO expert with a focus on keyword stemming, you must derive and choose the most appropriate stemmed variations from the keywords provided in this list: {unique_keywords_string}. Understand the core meaning and concept of each keyword, and then incorporate these stemmed variations intuitively and naturally across the entire text.\n"
    
    if app_settings['use_seo_package'] and seo_settings["wiki_links"]:
        prompt += f"Make sure to add the {wikipedia_link} at your text only one time accross the entire text! It is a must!\n"
    prompt += "Do not craft questions!\n"
        
    prompt += generate_default_prompts_end(app_settings, seo_settings)
    return prompt

def compile_properties_prompt(app_settings, seo_settings, target_category_name, prop_output, unique_keywords_string):
    """
    Generate content for properties of the category.
    """
    prompt = generate_default_prompts(app_settings, seo_settings, target_category_name, unique_keywords_string)
    prompt += "Use random formatting for each of the properties you are writing. Make sure that each of them are well presented!\n"
    prompt += "Key Features & Characteristics:\n"
    prompt += f"List characteristics buyers should consider when purchasing from {target_category_name} category. Integrate specific properties and associated values and links from your dataset: {prop_output}\n"
    prompt += "For each characteristic offer a general excper description.\n"
    prompt += f"- Discuss its importance and how it might influence the user's experience in the context of products at {target_category_name} category.\n"
    prompt += f"- Provide different options or variations within that characteristic and explain the pros and cons of each.\n"
    prompt += "*** Only for your internal usage ***: You are working on Category properties part of the entire category description. Befor that was Introduction. Below are eventually other parts such as: Highlight of the Top brands and Best selling/quality product, FAQ, etc.\n"
    if app_settings['use_seo_package'] and seo_settings["generic_keywords"]:
        prompt += f"As an SEO expert with a focus on keyword stemming, you must derive and choose the most appropriate stemmed variations from the keywords provided in this list: {unique_keywords_string}. Understand the core meaning and concept of each keyword, and then incorporate these stemmed variations intuitively and naturally across the entire text.\n"
    
    prompt += generate_default_prompts_end(app_settings, seo_settings)
    return prompt

def compile_product_levels_intro_prompt(category_settings, target_category_name, entry_level_products, mid_size_products, hi_end_products, app_settings, seo_settings, unique_keywords_string):

    prompt = (f"You are SEO and Copywriter and are writing in {app_settings['language']} language. Craft an introduction for the Best selling {target_category_name}. It have to be sales orientated general "
              "intro that announce entry-level, mid-level and hi-end products. It will explain what users can expect form the section below. "
              "It should be a maximum of 100-150 words. "
              "Do not welcome the user or thank him for reading the description. Do not conclude or summarize the description. "
              "At the begining and at the end add this: <br>\n")

    return prompt

def compile_product_levels_entry_prompt(category_settings, target_category_name, entry_level_products, mid_size_products, hi_end_products, app_settings, seo_settings, unique_keywords_string):
    """
    Generate content for the second section based on the information and prompts provided.
    """

    prompt = generate_default_prompts(app_settings, seo_settings, target_category_name, unique_keywords_string)      

    prompt += "Follow the instructions carfully and step by step!\n"
    prompt += f"Write creative heading about: Best selling Entry-Level product. You can use appropriate keyword from the provided list.\n"

    prompt += f"Instructions for each product:\n"
    prompt += ("Use the following example of the HTML structure for each of the entry-level products you are reviewing:\n"
           "<div style=\"display: flex; justify-content: center; align-items: center; flex-wrap: wrap;\">"
           "<a href=\"PRODUCT_URL\">"
           "<img src=\"IMAGE_URL\" alt=\"PRODUCT_NAME\" width=\"200px\">"
           "</a>"
           "<p style=\"padding-left: 25px;\" class=\"col-sm-10 col-md-9 col-lg-8\">"
           f"Write a review, recommendations, expert insights and highlight for each of all budget-friendly products from this dataset: {entry_level_products}."
           "The text has to offer guidance to potential buyers without stating exact prices but orientation about the price range."
           "When you mention the product name use a link to it: <a href=\"PRODUCT_URL\"><strong>PRODUCT_NAME</strong></a></p></div>")


    if app_settings['use_seo_package'] and seo_settings["e_e_a_t"]:
        prompt += ("Knowing the E-E-A-T standard, craft the entire description by following Google guidelines:\n"
                    "Does the content demonstrate first-hand experience?\nDoes the content demonstrate in-the-field experience?\n"
                    "How well does the content share a personal experience, perspective, or feelings on a topic?\n"
                    "Does content also demonstrate that it was produced with some degree of experience, such as actual product use, or communicating what a person experienced?\n"
                    "How original is the content?\nDoes this content demonstrate a depth of expertise in this topic?\n")
    prompt += "*** Only for your internal usage ***: You are working on Best selling entry-level products review, which is a part of the entire category description. Befor that was Introduction, Category characteristics. Below are eventually other parts such as: Highlight of the Top brands, FAQ, etc.\n"
    if app_settings['use_seo_package'] and seo_settings["generic_keywords"]:
        prompt += f"As an SEO expert with a focus on keyword stemming, you must derive and choose the most appropriate stemmed variations from the keywords provided in this list: {unique_keywords_string}. Understand the core meaning and concept of each keyword, and then incorporate these stemmed variations intuitively and naturally across the entire text.\n"
    
    prompt += "Highlight the best product in another text block by adding this tag <br>. Based on expert analysis, emphasize the best hi-end product and explain why. Do not forget to link the product name with its coresponding product_url. Do not make a heading!\n"
    prompt += "At the end add 2 HTML tag: <br><br>\n"
    prompt += generate_default_prompts_end(app_settings, seo_settings)
    
    return prompt

def compile_product_levels_mid_prompt(category_settings, target_category_name, entry_level_products, mid_size_products, hi_end_products, app_settings, seo_settings, unique_keywords_string):
    """
    Generate content for the second section based on the information and prompts provided.
    """

    prompt = generate_default_prompts(app_settings, seo_settings, target_category_name, unique_keywords_string)      

    prompt += "Follow the instructions carfully and step by step!\n"
    prompt += f"Write creative heading about: Mid-Level {target_category_name}. You can use appropriate keyword from the provided list:\n"

    prompt += f"Instructions for each product:\n"
    prompt += ("Use the following example of the HTML structure for each of the products you are reviewing:\n"
           "<div style=\"display: flex; justify-content: center; align-items: center; flex-wrap: wrap;\">"
           "<a href=\"PRODUCT_URL\">"
           "<img src=\"IMAGE_URL\" alt=\"PRODUCT_NAME\" width=\"200px\">"
           "</a>"
           "<p style=\"padding-left: 25px;\" class=\"col-sm-10 col-md-9 col-lg-8\">"
           f"Write a review, recommendations, expert insights and highlight for each of all mid-level products from this dataset: {mid_size_products}."
           "The text has to offer guidance to potential buyers without stating exact prices but orientation about the price range."
           "When you mention the product name use a link to it: <a href=\"PRODUCT_URL\"><strong>PRODUCT_NAME</strong></a></p></div>")




    if app_settings['use_seo_package'] and seo_settings["e_e_a_t"]:
        prompt += ("Knowing the E-E-A-T standard, craft the entire description by following Google guidelines:\n"
                    "Does the content demonstrate first-hand experience?\nDoes the content demonstrate in-the-field experience?\n"
                    "How well does the content share a personal experience, perspective, or feelings on a topic?\n"
                    "Does content also demonstrate that it was produced with some degree of experience, such as actual product use, or communicating what a person experienced?\n"
                    "How original is the content?\nDoes this content demonstrate a depth of expertise in this topic?\n")
    prompt += "*** Only for your internal usage ***: You are working on Best selling mid-level products review, which is a part of the entire category description. Befor that was Introduction, Category characteristics. Below are eventually other parts such as: Highlight of the Top brands, FAQ, etc.\n"
    if app_settings['use_seo_package'] and seo_settings["generic_keywords"]:
        prompt += f"As an SEO expert with a focus on keyword stemming, you must derive and choose the most appropriate stemmed variations from the keywords provided in this list: {unique_keywords_string}. Understand the core meaning and concept of each keyword, and then incorporate these stemmed variations intuitively and naturally across the entire text.\n"
    
    prompt += "Highlight the best product in another text block by adding this tag <br>. Based on expert analysis, emphasize the best hi-end product and explain why. Do not forget to link the product name with its coresponding product_url. Do not make a heading!\n"
    prompt += "At the end add 2 HTML tag: <br><br>\n"
    prompt += generate_default_prompts_end(app_settings, seo_settings)

    return prompt

def compile_product_levels_high_prompt(category_settings, target_category_name, entry_level_products, mid_size_products, hi_end_products, app_settings, seo_settings, unique_keywords_string):
    """
    Generate content for the second section based on the information and prompts provided.
    """


    prompt = generate_default_prompts(app_settings, seo_settings, target_category_name, unique_keywords_string)      

    prompt += "Follow the instructions carfully and step by step!\n"
    prompt += f"Write creative heading about: High-End (Flagships) Premium {target_category_name} with top-tier features. You can use appropriate keyword from the provided list.\n"

    prompt += f"Instructions for each product:\n"
    prompt += ("Use the following example of the HTML structure for each of the hi-end products you are reviewing:\n"
           "<div style=\"display: flex; justify-content: center; align-items: center; flex-wrap: wrap;\">"
           "<a href=\"PRODUCT_URL\">"
           "<img src=\"IMAGE_URL\" alt=\"PRODUCT_NAME\" width=\"200px\">"
           "</a>"
           "<p style=\"padding-left: 25px;\" class=\"col-sm-10 col-md-9 col-lg-8\">"
           f"Write a review, recommendations, expert insights and highlight for each of hi-end products from this dataset: {hi_end_products}."
           "The text has to offer guidance to potential buyers without stating exact prices but orientation about the price range."
           "When you mention the product name use a link to it: <a href=\"PRODUCT_URL\"><strong>PRODUCT_NAME</strong></a></p></div>")


    if app_settings['use_seo_package'] and seo_settings["e_e_a_t"]:
        prompt += ("Knowing the E-E-A-T standard, craft the entire description by following Google guidelines:\n"
                    "Does the content demonstrate first-hand experience?\nDoes the content demonstrate in-the-field experience?\n"
                    "How well does the content share a personal experience, perspective, or feelings on a topic?\n"
                    "Does content also demonstrate that it was produced with some degree of experience, such as actual product use, or communicating what a person experienced?\n"
                    "How original is the content?\nDoes this content demonstrate a depth of expertise in this topic?\n")
    prompt += "*** Only for your internal usage ***: You are working on Best selling hi-end products review, which is a part of the entire category description. Befor that was Introduction, Category characteristics. Below are eventually other parts such as: Highlight of the Top brands, FAQ, etc.\n"
    if app_settings['use_seo_package'] and seo_settings["generic_keywords"]:
        prompt += f"As an SEO expert with a focus on keyword stemming, you must derive and choose the most appropriate stemmed variations from the keywords provided in this list: {unique_keywords_string}. Understand the core meaning and concept of each keyword, and then incorporate these stemmed variations intuitively and naturally across the entire text.\n"
    
    prompt += "Highlight the best product in another text block by adding this tag <br>. Based on expert analysis, emphasize the best hi-end product and explain why. Do not forget to link the product name with its coresponding product_url. Do not make a heading!\n"
    prompt += "At the end add 2 HTML tag: <br><br>\n"

    prompt += generate_default_prompts_end(app_settings, seo_settings)

    return prompt

def compile_top_brands(app_settings, seo_settings, target_category_name, top_brands, unique_keywords_string):
    """
    Generate content for the third section based on the information and prompts provided.
    """
    prompt = generate_default_prompts(app_settings, seo_settings, target_category_name, unique_keywords_string)
    prompt += f"Best Brands in the {target_category_name} category:\n"
    prompt += "For each brand:\n"
    prompt += f"Provide a brief history or background of the brand in the context of producing {target_category_name}.\n"
    prompt += f"Discuss its reputation and what sets it apart from competitors for the category {target_category_name}\n"
    if app_settings['use_seo_package'] and seo_settings["top_brands_links"] != True:
        prompt += "Highlight the most purchased or popular brands/models within that category. This would be based on sales data"
        prompt += f"Highlighting Top Brands: {top_brands}. Do not use the URLs.\n"
    elif app_settings['use_seo_package'] and seo_settings["top_brands_links"] == True:
        prompt += f"Highlighting Top Brands: {top_brands}. With that list, do not make the name of the brand as title, insted incorporate it into the text. Make a hyperlink text for each of the top brands, and this anchor text should always include: the Product category and the Brand name, and a reference to the word 'price' or 'affordable'. For example, if the brand name is 'Sony' and the category is 'Soundbars', the hyperlink text will be 'Sony soundbar price' or 'Affordable Sony Soundbars'.\n"
    prompt += "*** Only for your internal usage ***: You are working on Top brands part of the entire category description. Befor that was Introduction, Category characteristics, best selling and quality products. Bellow are eventually Other related categories and FAQ section\n"
    if app_settings['use_seo_package'] and seo_settings["generic_keywords"]:
        prompt += f"As an SEO expert with a focus on keyword stemming, you must derive and choose the most appropriate stemmed variations from the keywords provided in this list: {unique_keywords_string}. Understand the core meaning and concept of each keyword, and then incorporate these stemmed variations intuitively and naturally across the entire text.\n"
     
    prompt += generate_default_prompts_end(app_settings, seo_settings)

    return prompt

def compile_category_levels(app_settings, seo_settings, top_level_category, same_level_categories, sub_level_categories, unique_keywords_string, target_category_name):
    """
    Generate content for the third section based on the information and prompts provided.
    """
    prompt = generate_default_prompts(app_settings, seo_settings, target_category_name, unique_keywords_string)
    prompt += "Do not make heading for this section:\n"
    prompt += f"Incorporate related category pages to {target_category_name} within the guide to improve navigation and boost SEO.\n"
    prompt += f"Select only the most relevant categories to {target_category_name}. That way you will create supperbeb customers experience.\n"
    parts = []

    if app_settings['use_seo_package'] and top_level_category:
        parts.append(f'make a link to the parent category: {top_level_category} and explain why you are giving a link to it.')

    if app_settings['use_seo_package'] and same_level_categories:
        parts.append(f"add links of the most appropriate same level categories: {same_level_categories} because they are related to {target_category_name}.")

    if app_settings['use_seo_package'] and sub_level_categories:
        parts.append(f"and links of the most appropriate sub-categories: {sub_level_categories}. To narrow down the search and make it easier for the user to find the right product.")

    if parts:
        prompt += f"At your description, make sure to {' '.join(parts)}.\n"
    prompt += "*** Only for your internal usage ***: You are working on Related categories part of the entire category description. Befor that was Introduction, Category characteristics, best selling and quality products. Bellow is eventually FAQ section\n"
    if app_settings['use_seo_package'] and seo_settings["generic_keywords"]:
        prompt += f"As an SEO expert with a focus on keyword stemming, you must derive and choose the most appropriate stemmed variations from the keywords provided in this list: {unique_keywords_string}. Understand the core meaning and concept of each keyword, and then incorporate these stemmed variations intuitively and naturally across the entire text.\n"
     
    prompt += generate_default_prompts_end(app_settings, seo_settings)

    return prompt

def compile_additional_info_prompt(app_settings, category_settings, seo_settings, unique_keywords_string, target_category_name):
    """
    Generate content for the third section based on the information and prompts provided.
    """

    additional_instructions = category_settings['additional_instructions']

    prompt = generate_default_prompts(app_settings, seo_settings, target_category_name, unique_keywords_string='')

    prompt += f"This section is for adding additional info at the category description of {target_category_name}\n"
    prompt += f"This are the topics to write, separated by comma: {additional_instructions}. Each topic is highly important and its goal is to be informative.\n"
    
    if app_settings['use_seo_package'] and seo_settings["e_e_a_t"]:
        prompt += ("Knowing the E-E-A-T standard, craft the entire description by following Google guidelines:\n"
                    "Does the content demonstrate first-hand experience?\nDoes the content demonstrate in-the-field experience?\n"
                    "How well does the content share a personal experience, perspective, or feelings on a topic?\n"
                    "Does content also demonstrate that it was produced with some degree of experience, such as actual product use, or communicating what a person experienced?\n"
                    "How original is the content?\nDoes this content demonstrate a depth of expertise in this topic?\n")
    
    prompt += generate_default_prompts_end(app_settings, seo_settings)

    return prompt

def construct_messages_for_section(system_prompt, section_prompt):
    """
    Construct the messages list given a system prompt and the section prompt.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": section_prompt},
    ]
    return messages

