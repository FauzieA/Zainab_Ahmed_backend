from django.urls import path
from . import views

urlpatterns = [
    # Public Client Facing Mappings
    path('meta/', views.get_booking_meta, name='booking-meta'),
    path('intent/', views.create_booking_intent, name='booking-intent'),
    path('webhook/', views.paystack_webhook, name='paystack-webhook'),
    
    # Core Admin Control Cluster
    path('admin-token/', views.admin_token_login, name='admin-token-login'),
    path('admin-dashboard-data/', views.get_admin_dashboard_data, name='admin-dashboard-data'),
    path('admin-slots/', views.admin_create_slot, name='admin-create-slot'),
    path('admin-slots-delete/<int:slot_id>/', views.admin_delete_slot, name='admin-delete-slot'),
    path('admin-cancel/', views.admin_cancel_booking, name='admin-cancel'),
    path('admin-reschedule/', views.admin_reschedule_booking, name='admin-reschedule'),
    path('admin-manual-reserve/', views.admin_manual_reserve, name='admin-manual-reserve'),
    path('admin-blackout/', views.admin_blackout_dates, name='admin-blackout'),
    
    # NEW SYSTEM LAYOUT ROUTE TARGETS
    path('config/', views.get_system_config, name='get-system-config'),
    path('config/update-price/', views.update_system_price, name='update-system-price'),
    path('config/update-content/', views.update_system_content, name='update-system-content'),

    
]