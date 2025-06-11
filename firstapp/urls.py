from django.urls import path
from .views import *

urlpatterns = [
    path('',welcome),
    path("register/", register),
    path('employee/',Demodb.as_view()),
    path("download-data/",DownloadData.as_view()),
    
]