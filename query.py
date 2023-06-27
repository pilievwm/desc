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

def processed(db, Processed, project_id, product_id, app_settings, task_id, response, page_url):  # Update the argument list
    new_processed = Processed(
        project_id=project_id,
        record_id=product_id,
        model=app_settings['model'],
        task_id=task_id,
        output=response['choices'][0]['message']['content'],
        page_url=page_url  # Add this line to store the page URL
    )

    db.session.add(new_processed)
    db.session.commit()
