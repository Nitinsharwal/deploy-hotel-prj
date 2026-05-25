"""Routes for /super-admin/. All views in super_admin.py are @superuser-only."""

from django.urls import path

from . import super_admin as views

urlpatterns = [
    path("", views.dashboard, name="super_dashboard"),
    path("vendors/<int:vendor_id>/", views.vendor_detail, name="super_vendor_detail"),
    path("vendors/<int:vendor_id>/verify/", views.toggle_verified, name="super_toggle_verified"),
    path("vendors/<int:vendor_id>/charges/new/", views.create_charge, name="super_create_charge"),
    # `edit` must come BEFORE the <str:action> catchall, otherwise it gets
    # routed into update_charge_status with action='edit'.
    path("charges/<int:charge_id>/edit/", views.edit_charge, name="super_edit_charge"),
    path(
        "charges/<int:charge_id>/<str:action>/",
        views.update_charge_status,
        name="super_update_charge",
    ),
]
