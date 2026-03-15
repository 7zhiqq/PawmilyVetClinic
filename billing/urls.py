from django.urls import path

from . import views

urlpatterns = [
    path("billing/", views.billing_list, name="billing_list"),
    path("billing/<int:pk>/", views.billing_detail, name="billing_detail"),
    path("billing/<int:pk>/add-item/", views.billing_add_line_item, name="billing_add_line_item"),
    path("billing/<int:pk>/remove-item/<int:item_id>/", views.billing_remove_line_item, name="billing_remove_line_item"),
    path("billing/<int:pk>/add-payment/", views.billing_add_payment, name="billing_add_payment"),
    path("billing/<int:pk>/submit-payment/", views.billing_submit_payment, name="billing_submit_payment"),
    path("billing/<int:pk>/verify-payment/<int:payment_id>/", views.billing_verify_payment, name="billing_verify_payment"),
]
