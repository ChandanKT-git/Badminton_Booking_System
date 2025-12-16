from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register_view, name='register'),
    path('accounts/login/', views.login_view, name='login'),
    path('accounts/logout/', views.logout_view, name='logout'),
    path('booking/', views.booking_page, name='booking'),
    path('booking/history/', views.booking_history, name='booking_history'),
    
    # API endpoints
    path('api/availability/', views.api_check_availability, name='api_availability'),
    path('api/calculate-price/', views.api_calculate_price, name='api_calculate_price'),
    path('api/confirm-booking/', views.confirm_booking, name='api_confirm_booking'),
    path('api/join-waitlist/', views.join_waitlist, name='api_join_waitlist'),
    path('api/remove-waitlist/', views.remove_from_waitlist, name='api_remove_waitlist'),
    path('api/cancel-booking/', views.cancel_booking, name='api_cancel_booking'),
]

