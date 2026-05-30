from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from users.views import SignupPageView
from irrbb_app.views import LogOutView
urlpatterns = [path('admin/', admin.site.urls), path('register/', SignupPageView.as_view(), name='register'), path('login/', auth_views.LoginView.as_view(template_name='irrbb_app/login.html'), name='login'), path('logout/', LogOutView, name='logout'), path('users/', include('users.urls', namespace='users')), path('', include('irrbb_app.urls'))]