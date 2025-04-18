from django.urls import path, include
from allauth.socialaccount.providers.google.views import oauth2_login as google_login
from allauth.socialaccount.providers.github.views import oauth2_login as github_login
from allauth.socialaccount.providers.microsoft.views import oauth2_login as microsoft_login

app_name = 'oauth'

urlpatterns = [
    path('google/', google_login, name='google'),
    path('github/', github_login, name='github'),
    path('microsoft/', microsoft_login, name='microsoft'),
    # Ajoutez les autres URLs nécessaires
]