from django.urls import path

from . import views

urlpatterns = [
    path("", views.start, name="start"),
    path("dashboard/", views.home, name="dashboard"),
    path("upload/", views.upload_contracts, name="upload_contracts"),
    path("resultados/", views.results_history, name="results_history"),
    path("resultados/<int:pk>/", views.DetailView.as_view(), name="detail"),
    path("download_template/", views.download_template, name="download_template"),
]
