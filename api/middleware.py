# myapp/middleware.py
import logging
from django.http import JsonResponse


logger = logging.getLogger(__name__)

class Handle500ErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            print(response)
        except Exception as e:
            # logger.info(f"Unhandled exception: {str(e)}", exc_info=True)
            print(e,"=============")
            return JsonResponse(
                {
                    'error': True,
                    'message': 'An internal server error occurred. Please try again later.',
                    'status_code': 500
                },
                status=500
            )
        return response
