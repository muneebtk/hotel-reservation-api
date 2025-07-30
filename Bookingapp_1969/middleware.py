import os
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.utils.module_loading import import_string

# Lazily import Django's AnonymousUser and Token model
def get_anonymous_user():
    return import_string('django.contrib.auth.models.AnonymousUser')

def get_token_model():
    return import_string('rest_framework.authtoken.models.Token')

class WebSocketAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_params = parse_qs(scope["query_string"].decode())

        # 🔹 1. Check for Token Authentication (Flutter App)
        token_key = query_params.get("token", [None])[0]
        if token_key:
            user = await self.get_user_from_token(token_key)
        else:
            # 🔹 2. Use Django Session Authentication (WebApp)
            user = scope.get("user", get_anonymous_user()())

        scope["user"] = user
        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user_from_token(self, token_key):
        """Retrieve user from Token or return AnonymousUser."""
        Token = get_token_model()  # Lazily load the Token model
        try:
            token = Token.objects.get(key=token_key)
            return token.user
        except Token.DoesNotExist:
            return get_anonymous_user()()