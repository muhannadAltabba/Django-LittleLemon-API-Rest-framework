from rest_framework import generics, status, mixins, viewsets
from rest_framework.response import Response
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework.decorators import permission_classes, throttle_classes
from .models import MenuItem, Cart, Order, OrderItem
from django.contrib.auth.models import User, Group
from .serializers import MenuItemSerializer, UserSerializer, CartSerializer, OrderSerializer, OrderItemSerializer
from django.shortcuts import  get_object_or_404


class PatchedDjangoModelPermissions(DjangoModelPermissions):
    perms_map = {
        'GET':['%(app_label)s.view_%(model_name)s'],
        'OPTIONS': [],
        'HEAD': [],
        'POST': ['%(app_label)s.add_%(model_name)s'],
        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],
        'DELETE': ['%(app_label)s.delete_%(model_name)s'],
    }


class MenuItemsView(generics.ListCreateAPIView):
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer
    throttle_classes = [AnonRateThrottle, UserRateThrottle]
    ordering_fields = ['price', 'inventory']
    search_fields = ['category__title']
    permission_classes = [DjangoModelPermissions]
    

class SingleItemView(generics.RetrieveUpdateDestroyAPIView):
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer
    throttle_classes = [AnonRateThrottle, UserRateThrottle]
    permission_classes = [DjangoModelPermissions]


class GroupUsersView(viewsets.GenericViewSet, mixins.CreateModelMixin, mixins.ListModelMixin, mixins.DestroyModelMixin):
    serializer_class = UserSerializer
    permission_classes = [PatchedDjangoModelPermissions]

    def get_queryset(self):
        return User.objects.all()

    def filter_queryset(self, queryset):
        qs = super(GroupUsersView, self).filter_queryset(self.get_queryset())
        group_name = self.kwargs['group_name']
        if group_name:
            return qs.filter(groups__name=group_name)
        return qs

    def add_to_group(self, request, *args, **kwargs):
        user = get_object_or_404(User, username=request.data['username'])
        group = get_object_or_404(Group, name=self.kwargs['group_name']) 
        group.user_set.add(user)
        return Response({'message': 'User added to group sucssefully'}, 200)


    def delete(self, request, *args, **kwargs):
        user = get_object_or_404(User, username=request.data['username'])
        group = get_object_or_404(Group, name=self.kwargs['group_name']) 
        group.user_set.remove(user)
        return Response({'message': 'User removed from group sucssefully'}, 200)


class CartItemsView(viewsets.GenericViewSet, mixins.CreateModelMixin, mixins.ListModelMixin, mixins.DestroyModelMixin):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Cart.objects.all()

    def filter_queryset(self, queryset):
        return super(CartItemsView, self).filter_queryset(self.get_queryset()).filter(user=self.request.user)
        
    def delete(self, request, *args, **kwargs):
        self.get_queryset().delete()
        return Response(status= status.HTTP_204_NO_CONTENT)


class OrdersView(generics.ListCreateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return Order.objects.all()
    
    def get(self, request, *args, **kwargs):
        user = self.request.user
        if user.groups.filter(name='manager').exists():
            return super().get(request, *args, **kwargs)
        elif user.groups.filter(name='delivery-crew').exists():
            orders = self.get_queryset().filter(delivery_crew=user)
        else:
            orders = self.get_queryset().filter(user=user)
        return Response(self.serializer_class(orders, many=True).data, status=status.HTTP_200_OK)
    
    def post(self, request, *args, **kwargs):
        cart = Cart.objects.filter(user=request.user)
        if cart.count() == 0:
            return Response({"message:": "no item in cart"})

        data = request.data.copy()
        total = self.calculate_total(cart)
        data['total'] = total
        data['user'] = self.request.user.id

        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            order = serializer.save()
            for item in cart:
                OrderItem.objects.create(menuitem=item.menuitem, quantity=item.quantity, 
                unit_price=item.unit_price, price=item.price, order=order)
            Cart.objects.filter(user=request.user).delete()

        return Response({'message': 'Order created sucssefully'}, status=status.HTTP_201_CREATED)

    def calculate_total(self, cart):
        total = 0
        for item in cart:
            total += item.price
        return total



class SingleOrderView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = OrderSerializer
    permission_classes = [DjangoModelPermissions]
    queryset = Order.objects.all()

    def get(self, request, *args, **kwargs):    
        try:
            if request.user == self.get_queryset().get(id=self.kwargs['pk']).user:
                return super().get(request, *args, **kwargs)
        except:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_401_UNAUTHORIZED)

    def put(self, request, *args, **kwargs):
        if request.user.groups.filter(name='manager').exists():
            try:
                order = self.get_queryset().get(id=self.kwargs['pk'])
            except:
                return Response(status=status.HTTP_404_NOT_FOUND)
            try:
                delivery_crew = User.objects.get(id=request.data['delivery_crew_id'])
                print(delivery_crew)
            except:
                return Response({'message': 'user not found'}, status=status.HTTP_404_NOT_FOUND)

            if delivery_crew.groups.filter(name='delivery-crew').exists():
                order.delivery_crew = delivery_crew
                order.save()
            else:
                return Response({'message': 'user not in delivery-crew group'}, status=status.HTTP_400_BAD_REQUEST)

            return Response(status=status.HTTP_202_ACCEPTED)
        return Response(status=status.HTTP_401_UNAUTHORIZED)
        

