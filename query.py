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