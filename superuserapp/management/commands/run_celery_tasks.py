from django.core.management.base import BaseCommand
from Bookingapp_1969.celery import update_completed_bookings, mark_promotions_inactive

class Command(BaseCommand):
    help = 'Run specified Celery tasks'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting Celery tasks...")

        # Trigger the Celery tasks
        update_completed_bookings.delay()
        self.stdout.write("Triggered: update_completed_bookings task.")

        mark_promotions_inactive.delay()
        self.stdout.write("Triggered: mark_promotions_inactive task.")

        self.stdout.write("Tasks have been dispatched.")
