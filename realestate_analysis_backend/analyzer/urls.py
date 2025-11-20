from django.urls import path
from .views import AnalyzeAPIView, DownloadXLSXAPIView

urlpatterns = [
    path('analyze/', AnalyzeAPIView.as_view(), name='analyze'),
    path('download-xlsx/', DownloadXLSXAPIView.as_view(), name='download-xlsx'),
]
