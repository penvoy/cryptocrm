from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth.forms import UserCreationForm

from .serializers import UserSerializer


class UserViewSet(viewsets.ViewSet):
    """
    Методы для создания, удаления и листинга пользователей
    """
    @action(detail=False, methods=['post', 'get'])
    def list_and_create(self, request):

        if request.data:
            print(request.data)
            form = UserCreationForm(data=request.data)

            print(form)

            if form.is_valid():
                print("saved")
                form.save()
                
        form = UserCreationForm()

        queryset = User.objects.all()
        serializer = UserSerializer(queryset, many=True)

        return render(request, 'users/users.html', context={"users": serializer.data, "form": form})

    @action(detail=True, methods=['post', 'delete'])
    def delete(self, request, pk=None):
        if not request.user.is_superuser:
            return render(request, 'errors/500.html', context={"error": "Недостаточно прав"})
        
        user = User.objects.filter(id=pk).first()
        if not user:
            return render(request, 'errors/404.html', context={"error": "Пользователь не найден"})
        
        # удаляем,если он есть
        user.delete()

        return self.list_and_create(request)
