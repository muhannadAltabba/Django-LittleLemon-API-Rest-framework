from django.urls import path
from . import views

urlpatterns = [
    path('menu-items', views.MenuItemsView.as_view()),
    path('menu-items/<int:pk>', views.SingleItemView.as_view()),
    path('groups/<str:group_name>/users', views.GroupUsersView.as_view({'get':'list', 'post': 'add_to_group', 'DELETE':'delete'})),
    path('cart/menu-items', views.CartItemsView.as_view({'get':'list', 'post': 'create', 'DELETE':'delete'})),
    path('orders', views.OrdersView.as_view()),
    path('orders/<int:pk>', views.SingleOrderView.as_view()),
    
]