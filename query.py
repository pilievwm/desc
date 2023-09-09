import json
from datetime import datetime
import pytz

def sofia_now():
    """Get the current datetime in Sofia timezone."""
    utc_dt = datetime.utcnow().replace(tzinfo=pytz.utc)
    sofia_tz = pytz.timezone('Europe/Sofia')
    return utc_dt.astimezone(sofia_tz)

def statistics(db, Statistics, project_id, product_id, app_settings, task_id, response, cost, test_mode):
    new_stat = Statistics(
        project_id=project_id,
        record_id=product_id,
        model=app_settings['model'],
        test_mode=test_mode,
        task_id=task_id,
        prompt_tokens=response['usage']['prompt_tokens'],
        completion_tokens=response['usage']['completion_tokens'],
        total_tokens=response['usage']['total_tokens'],
        cost=cost
    )

    db.session.add(new_stat)
    db.session.commit()

def processed(db, Processed, project_id, product_id, app_settings, task_id, response, page_url, title=None):  # Added title parameter
    new_processed = Processed(
        project_id=project_id,
        record_id=product_id,
        model=app_settings['model'],
        task_id=task_id,
        output=response['choices'][0]['message']['content'],
        page_url=page_url,  # Store the page URL
        title=title  # Store the title
    )

    db.session.add(new_processed)
    db.session.commit()

"""
save_processed_product:
    Saves or updates a processed product record in the database.

    Args:
    - db (object): The database session object.
    - Processed (class): The ORM model class for the processed product.
    - project_id (int/str): The ID of the project.
    - product_id (int/str): The ID of the product.
    - **kwargs (dict, optional): Additional fields to be saved or updated. If a field's value is a dictionary, it will be serialized to a JSON string.

    Usage:
    The function can either update an existing product or create a new one. If the product already exists in the database with the given project_id and product_id, it will be updated. Otherwise, a new product will be created.

    Example:
    save_processed_product(db, Processed, project_id=1, product_id=2, task_id=123, description="Some description", page_url="http://example.com")
    
    Notes:
    - If a field in kwargs is expected to be a JSON, ensure its value is a dictionary. It will be serialized before saving.
    - Only the fields passed in kwargs will be updated if the product already exists.
"""

def save_processed_product(db, Processed, project_id, product_id, **kwargs):
    # Ensure proper data types
    project_id = int(project_id)
    product_id = int(product_id)

    # Check if an entry with the given criteria exists
    existing_product = db.session.query(Processed).filter_by(project_id=project_id, record_id=product_id).first()

    # Serialize any fields that are expected to be JSON
    for key, value in kwargs.items():
        if isinstance(value, dict):
            kwargs[key] = json.dumps(value, ensure_ascii=False)

    if existing_product:
        # If created_at field is set, update the updated_at field to current datetime
        if existing_product.created_at:
            existing_product.updated_at = sofia_now()
        
        # If published is set to 1, update the published_at field to current datetime
        if kwargs.get('published') == 1:
            existing_product.published_at = sofia_now()

        # Update only the fields passed in kwargs
        for key, value in kwargs.items():
            setattr(existing_product, key, value)
    else:
        # Create a new product
        new_product = Processed(
            project_id=project_id,
            record_id=product_id,
            **kwargs
        )
        db.session.add(new_product)

    db.session.commit()




def save_processed_category(db, ProcessedCategory, project_id, category_id, **kwargs):
    # Ensure proper data types
    project_id = int(project_id)
    category_id = int(category_id)

    # Check if an entry with the given criteria exists
    existing_category = db.session.query(ProcessedCategory).filter_by(project_id=project_id, category_id=category_id).first()

    # Serialize any fields that are expected to be JSON
    for key, value in kwargs.items():
        if isinstance(value, dict):
            kwargs[key] = json.dumps(value, ensure_ascii=False)

    if existing_category:
        # If category_created_at field is set, update the category_updated_at field to current datetime
        if existing_category.category_created_at:
            existing_category.category_updated_at = sofia_now()
        # Update only the fields passed in kwargs
        for key, value in kwargs.items():
            setattr(existing_category, key, value)
    else:
        # Create a new category
        new_category = ProcessedCategory(
            project_id=project_id,
            category_id=category_id,
            **kwargs
        )
        db.session.add(new_category)

    db.session.commit()

