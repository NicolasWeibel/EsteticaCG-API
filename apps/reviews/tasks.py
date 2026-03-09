from celery import shared_task

from .services import sync_google_reviews


@shared_task
def sync_google_reviews_task():
    return sync_google_reviews()
