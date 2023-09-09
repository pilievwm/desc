#models.py

from flask_login import UserMixin
from datetime import datetime

def create_user_class(db):
    class User(UserMixin, db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(100), nullable=False)
        email = db.Column(db.String(100), nullable=False, unique=True)
        super_user = db.Column(db.Boolean, default=False)
        projects = db.relationship('Project', backref='user', lazy=True, cascade="all, delete-orphan")
    return User


def create_statistics(db):
    class Statistics(db.Model):
        __tablename__ = 'statistics'
        id = db.Column(db.Integer, primary_key=True)
        project_id = db.Column(db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'), nullable=False)
        task_id = db.Column(db.Integer, nullable=True)
        model = db.Column(db.String(128), nullable=True)
        test_mode = db.Column(db.Integer , nullable=True)
        record_id = db.Column(db.Integer, nullable=False)
        datetime = db.Column(db.DateTime, default=datetime.utcnow)
        prompt_tokens = db.Column(db.Integer, nullable=False, default=0)
        completion_tokens = db.Column(db.Integer, nullable=False, default=0)
        total_tokens = db.Column(db.Integer, nullable=False, default=0)
        cost = db.Column(db.Float, nullable=False, default=0.0)
    return Statistics

def create_processed(db):
    class Processed(db.Model):
        __tablename__ = 'processed'
        id = db.Column(db.Integer, primary_key=True)
        project_id = db.Column(db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'), nullable=False)
        task_id = db.Column(db.Integer, nullable=True)
        model = db.Column(db.String(128), nullable=True)
        title = db.Column(db.Text, nullable=True)
        meta_title = db.Column(db.Text, nullable=True)
        meta_description = db.Column(db.Text, nullable=True)
        description = db.Column(db.Text, nullable=True)
        short_description = db.Column(db.Text, nullable=True)
        record_id = db.Column(db.Integer, nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow)
        output = db.Column(db.Text, nullable=True)
        page_url = db.Column(db.Text, nullable=True)  # Add this line to store the page URL
        url_handle = db.Column(db.Text, nullable=True)  # Add this line to store the URL handle
        published = db.Column(db.Boolean, default=False)
        published_at = db.Column(db.DateTime, default=datetime.utcnow)
        token_count = db.Column(db.Integer, nullable=True)

    return Processed


def create_project_class(db):
    class Project(db.Model):
        __tablename__ = 'project'
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
        x_cloudcart_apikey = db.Column(db.String(128))
        enable_product_description = db.Column(db.Boolean)
        enable_generate_meta_description = db.Column(db.Boolean)
        enable_product_short_description = db.Column(db.Boolean)
        model = db.Column(db.String(128))
        temperature = db.Column(db.Integer, nullable=True)
        store_url = db.Column(db.String(128))
        website_name = db.Column(db.String(128), nullable=True)
        use_seo_package = db.Column(db.Boolean)
        currency = db.Column(db.String(128))
        length = db.Column(db.Integer)
        test_mode = db.Column(db.Boolean)
        print_prompt = db.Column(db.Boolean)
        only_active = db.Column(db.Boolean)
        skip_products_with_description = db.Column(db.Integer)
        specific_product = db.Column(db.String(128))
        only_category = db.Column(db.String(128))
        only_category_name = db.Column(db.String(128))
        only_vendor = db.Column(db.String(128))
        only_vendor_name = db.Column(db.String(128))
        language = db.Column(db.String(128))
        niche = db.Column(db.String(128))
        free_delivery_over = db.Column(db.Integer)
        mention_free_delivery_price = db.Column(db.Boolean)
        link_to_product = db.Column(db.Boolean)
        link_to_category = db.Column(db.Boolean)
        link_to_vendor = db.Column(db.Boolean)
        link_to_more_from_same_vendor_and_category = db.Column(db.Boolean)
        use_keywords = db.Column(db.Integer)
        keywords_density = db.Column(db.Integer)
        use_free_keywords = db.Column(db.String(128))
        link_keyword_to_product = db.Column(db.Boolean)
        link_keyword_density = db.Column(db.Integer)
        purpouse = db.Column(db.String(128))
        product_name = db.Column(db.Boolean)
        price_from = db.Column(db.Boolean)
        show_price = db.Column(db.Boolean)
        short_description = db.Column(db.Boolean)
        description = db.Column(db.Boolean)
        vendor_name = db.Column(db.Boolean)
        category_name = db.Column(db.Boolean)
        property_option_values = db.Column(db.Boolean)
        use_website_name = db.Column(db.Boolean)
        domain = db.Column(db.String(128))
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow)
        short_length = db.Column(db.Integer, nullable=True)
        short_temperature = db.Column(db.Float, nullable=True)
        short_language = db.Column(db.String(128), nullable=True)
        short_purpose = db.Column(db.String(128), nullable=True)
        short_product_name = db.Column(db.Boolean, nullable=True)
        short_short_description = db.Column(db.Boolean, nullable=True)
        short_vendor_name = db.Column(db.Boolean, nullable=True)
        short_category_name = db.Column(db.Boolean, nullable=True)
        short_property_option_values = db.Column(db.Boolean, nullable=True)
        short_use_website_name = db.Column(db.Boolean, nullable=True)
        short_additional_instructions = db.Column(db.Text, nullable=True)
        additional_instructions = db.Column(db.Text, nullable=True)
        in_progress = db.Column(db.Boolean, nullable=True)
        system_instructions = db.Column(db.Text, nullable=True)
        use_feature_desc = db.Column(db.Boolean, nullable=True)
        use_interesting_fact = db.Column(db.Boolean, nullable=True)
        use_hidden_benefit = db.Column(db.Boolean, nullable=True)
        e_e_a_t = db.Column(db.Boolean, nullable=True)
        user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
        statistics = db.relationship('Statistics', backref='project', lazy=True, cascade="all, delete-orphan")
        processed_records = db.relationship('Processed', backref='project', lazy=True, cascade="all, delete-orphan")

    return Project

def create_category_class(db):
    class CategorySetting(db.Model):
        __tablename__ = 'category_settings'

        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        project_id = db.Column(db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'), nullable=False)
        user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
        x_cloudcart_apikey = db.Column(db.String(128), nullable=False)
        url = db.Column(db.String(128), nullable=False)
        model = db.Column(db.String(128), nullable=False)
        seo_model = db.Column(db.String(128), nullable=True)
        website_name = db.Column(db.String(128), nullable=True)
        length = db.Column(db.Integer)
        temperature = db.Column(db.Integer)
        test_mode = db.Column(db.Boolean)
        print_prompt = db.Column(db.Boolean)
        print_scraped_data = db.Column(db.Boolean, default=False)
        language = db.Column(db.String(128), nullable=False)
        category_id = db.Column(db.Integer, nullable=True)
        category_name = db.Column(db.String(128), nullable=True)
        max_property_values = db.Column(db.Integer, nullable=True)
        max_keywords = db.Column(db.Integer, nullable=True)
        max_order_pages = db.Column(db.Integer, nullable=True)
        description_length = db.Column(db.Integer, nullable=True)
        include_sales_info = db.Column(db.Boolean, default=True)
        only_active_products = db.Column(db.Boolean, default=False)
        include_category_info = db.Column(db.Boolean, default=True)
        enable_category_description = db.Column(db.Boolean)
        enable_generate_meta_description = db.Column(db.Boolean)
        print_scraped_data = db.Column(db.Boolean, default=False)
        enable_faq_generation = db.Column(db.Boolean, default=False)
        add_faq = db.Column(db.Integer, default=0)
        add_best_selling_products = db.Column(db.Integer, default=0)
        add_top_brands = db.Column(db.Integer, default=0)
        number_images = db.Column(db.Integer, default=0)
        top_brands_links = db.Column(db.Boolean, default=False)
        generic_keywords = db.Column(db.Boolean, default=False)
        generate_keywords = db.Column(db.Boolean, default=False)
        e_e_a_t = db.Column(db.Boolean, default=False)
        wiki_faq_links = db.Column(db.Boolean, default=False)
        use_seo_package = db.Column(db.Boolean)
        additional_instructions = db.Column(db.Text, nullable=True)
        max_props = db.Column(db.Integer, nullable=True)
        in_progress = db.Column(db.Boolean, nullable=True)
        include_properties = db.Column(db.Boolean, default=False)
        include_category_name_at_headings = db.Column(db.Boolean, default=False)
        wiki_links = db.Column(db.Boolean, default=False)
        cat_links = db.Column(db.Boolean, default=False)
        include_intro = db.Column(db.Boolean, default=False)
        interesting_fact = db.Column(db.Boolean, default=False)
        category_ready = db.Column(db.Boolean, default=False)
        enable_additional_instructions = db.Column(db.Boolean, default=False)
        ### FAQ ###
        max_props_faq = db.Column(db.Integer, nullable=True)
        max_property_values_faq = db.Column(db.Integer, nullable=True)
        include_properties_faq = db.Column(db.Boolean, default=False)
        include_faq_info = db.Column(db.Boolean, default=False)
        add_top_brands_faq = db.Column(db.Integer, default=0)
        add_best_selling_products_faq = db.Column(db.Integer, default=0)
        include_category_info_faq = db.Column(db.Boolean, default=False)
        additional_instructions_faq = db.Column(db.Text, nullable=True)
        faq_length = db.Column(db.Integer, nullable=True)
        use_seo_faq_package = db.Column(db.Boolean, default=False)
        faq_top_brands_links = db.Column(db.Boolean, default=False)
        faq_category_links = db.Column(db.Boolean, default=False)
        faq_use_schema = db.Column(db.Boolean, default=False)
        faq_include_category_name_at_headings = db.Column(db.Boolean, default=False)
        faq_brand_link_authority = db.Column(db.Boolean, default=False)
        faq_wiki_link_authority = db.Column(db.Boolean, default=False)


        #############################
        use_main_keywords = db.Column(db.Text, default=False)
        processed_records = db.relationship('ProcessedCategory', backref='processed_category', lazy=True, cascade="all, delete-orphan")
    return CategorySetting


def create_processed_category_class(db):
    class ProcessedCategory(db.Model):
        __tablename__ = 'processed_category'
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        project_id = db.Column(db.Integer, db.ForeignKey('category_settings.id', ondelete='CASCADE', name='fk_processed_category_project_id'), nullable=False)
        category_id = db.Column(db.Integer, nullable=True)
        category_name = db.Column(db.String(128), nullable=True)
        category_structure = db.Column(db.Text, nullable=True)
        category_url = db.Column(db.Text, nullable=True)
        category_prompt = db.Column(db.Text, nullable=True)
        category_description = db.Column(db.Text, nullable=True)
        category_faqs = db.Column(db.Text, nullable=True)
        category_keywords = db.Column(db.Text, nullable=True)
        category_custom_keywords = db.Column(db.Text, nullable=True)
        category_test_mode = db.Column(db.Boolean)
        category_update = db.Column(db.Boolean, default=False)
        token_count = db.Column(db.Integer, nullable=True)
        category_created_at = db.Column(db.DateTime, default=datetime.utcnow)
        category_updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    return ProcessedCategory

def create_category_batch_class(db):
    class BatchCategory(db.Model):
        __tablename__ = 'batch_category'
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        project_id = db.Column(db.Integer, db.ForeignKey('category_settings.id', ondelete='CASCADE', name='fk_processed_category_project_id'), nullable=False)
        type = db.Column(db.String(128), nullable=True)
        kill_process = db.Column(db.Boolean, default=False)
        batch = db.Column(db.Boolean, default=False)
    return BatchCategory