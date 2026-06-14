from django.urls import path

from accounts import views

urlpatterns = [
    # Profile hub
    path("profile/", views.profile, name="profile"),
    path("profile/edit/", views.update_profile, name="update_profile"),
    path("login_page/", views.login_page, name="login_page"),
    # Superuser 2FA — only reachable when login_page populated the session.
    path("super_otp_verify/", views.super_otp_verify, name="super_otp_verify"),
    path("logout_user/", views.logout_user, name="logout_user"),
    path("register_page/", views.register_page, name="register_page"),
    path("send_otp/<str:email>/", views.send_otp, name="send_otp"),
    path("<str:email>/verify_otp/", views.verify_otp, name="verify_otp"),
    path("verify-account/<token>/", views.verify_email_token, name="verify_email_token"),
    path("forgot/", views.forgot_password, name="forgot_password"),
    path("forgot/otp/", views.forgot_password_otp, name="forgot_password_otp"),
    path("forgot/reset/<token>/", views.forgot_password_reset, name="forgot_password_reset"),
    path("vendor_login/", views.vendor_login, name="vendor_login"),
    path("vendor_logout/", views.vendor_logout, name="vendor_logout"),
    path("vendor_register/", views.vendor_register, name="vendor_register"),
    path("ven_dashboard/", views.ven_dashboard, name="ven_dashboard"),
    path("plan/", views.manage_plan, name="manage_plan"),
    path("plan/change/<slug:slug>/", views.change_plan, name="change_plan"),
    path("charges/<int:charge_id>/pay/", views.pay_charge, name="pay_charge"),
    path("charges/<int:charge_id>/done/", views.pay_charge_done, name="pay_charge_done"),
    path("add_hotel/", views.add_hotel, name="add_hotel"),
    path("<slug>/upload_images/", views.upload_images, name="upload_images"),
    path("delete_images/<id>", views.delete_images, name="delete_images"),
    path("edit_hotel/<slug>", views.edit_hotel, name="edit_hotel"),
    # Room CRUD (per hotel)
    path("hotels/<slug>/rooms/", views.manage_rooms, name="manage_rooms"),
    path("hotels/<slug>/rooms/add/", views.add_room, name="add_room"),
    path("hotels/<slug>/rooms/<int:room_id>/edit/", views.edit_room, name="edit_room"),
    path("hotels/<slug>/rooms/<int:room_id>/delete/", views.delete_room, name="delete_room"),
]
