from django.urls import path
from .views import *

urlpatterns = [
    path("", welcome),
    path("register/", register.as_view()),
    path("login/", login.as_view()),
    path("employee/", Demodb.as_view()),
]
