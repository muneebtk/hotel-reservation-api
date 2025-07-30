import os
import django
from django.conf import settings
from django.contrib.auth import get_user_model

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Bookingapp_1969.settings")
django.setup()

from vendor.models import PolicyCategory

def create_cancellation_policy():
    try:
        User = get_user_model()
        superuser = User.objects.filter(is_superuser=True).first()

        if not superuser:
            print("No superuser found. Cannot assign 'created_by' for 'Cancellation Policy'.")
            return

        cancellation_category = PolicyCategory.objects.filter(name="Cancellation Policy", policy_type="common").first()

        if not cancellation_category:
            common_category = PolicyCategory.objects.filter(policy_type='common').first()

            if common_category:
                PolicyCategory.objects.create(
                    name="Cancellation Policy",
                    policy_type="common",
                    created_by=superuser,
                )
                print('Successfully created the "Cancellation Policy" category in the common category.')
            else:
                print('Common category does not exist. Cannot create "Cancellation Policy".')
        else:
            print('"Cancellation Policy" category already exists under common category.')

    except Exception as e:
        print(f"Error during script execution: {e}")

if __name__ == "__main__":
    create_cancellation_policy()
