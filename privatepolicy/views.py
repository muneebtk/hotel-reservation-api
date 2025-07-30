import json
import os
import logging

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views import View
from Bookingapp_1969 import settings



logger = logging.getLogger(__name__)




class PrivacyPolicyView(View):
    def get(self, request):
        try:
            return render(request, "privacy-policy.html")
        except FileNotFoundError:
            logger.info(f"Privacy policy not found")
            return HttpResponse("Privacy policy not found", status=404)
class TermsAndConditionView(View):
    def get(self, request):
        try:
            return render(request, "terms-and-condition.html")
        except FileNotFoundError:
            logger.info(f"Terms and Condition not found")
            return HttpResponse("Terms and Condition not found", status=404)

class AboutUsView(View):
    def get(self, request):
        try:
            return render(request, "about-us.html")
        except FileNotFoundError:
            logger.info(f"About us not found")
            return HttpResponse("About us not found", status=404)

class Appleapp(View):
    def get(self, request):
        try:
            # Construct the file path
            file_path = os.path.join(settings.BASE_DIR, 'deep-link', 'IOS')
            
            # Open and read the JSON file
            with open(file_path, 'r') as file:
                assetlinks_data = json.load(file)
            
            # Return the JSON content
            return JsonResponse(assetlinks_data, safe=False)
        except FileNotFoundError:
            return JsonResponse({"error": "apple-app-site-association file not found"}, status=404)
        
class Androidapp(View):
    def get(self, request):
        try:
            # Construct the file path
            file_path = os.path.join(settings.BASE_DIR, 'deep-link', 'assetlinks.json')
            
            # Open and read the JSON file
            with open(file_path, 'r') as file:
                assetlinks_data = json.load(file)
            
            # Return the JSON content
            return JsonResponse(assetlinks_data, safe=False)
        except FileNotFoundError:
            return JsonResponse({"error": "assetlinks.json file not found"}, status=404)