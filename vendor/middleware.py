from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import activate
from django.conf import settings

class LanguageMiddleware(MiddlewareMixin):
    def process_request(self, request):
        language = request.session.get('django_language', settings.LANGUAGE_CODE)
        print(f"\n\n\n\n\n\n\n\n---------> language: {language}--------->\n\n\n\n\n\n\n\n")
        activate(language)
        request.LANGUAGE_CODE = language

