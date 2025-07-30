from rest_framework.permissions import IsAuthenticated
from user.models import Userdetails
#from django.contrib.auth import get_user_model
#User = get_user_model()

class AllowEndUserOnly(IsAuthenticated):
    # Create or read if user is authenticated

    def has_permission(self, request, view):
        return bool(
            Userdetails.objects.filter(user=request.user,user__is_deleted=False).exists()
        )
    def has_object_permission(self, request, view, obj):
        return bool(
            Userdetails.objects.filter(user=request.user,user__is_deleted=False).exists()
        )
   