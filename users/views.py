from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from rest_framework import viewsets, status
from rest_framework.response import Response

from .serializers import UserSerializer


class UserViewSet(viewsets.ViewSet):
    """
    Методы для создания, удаления и листинга пользователей
    """
    def list(self, request):
        queryset = User.objects.all()
        serializer = UserSerializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not request.user.is_superuser:
            return Response("Недостаточно прав", status=status.HTTP_403_FORBIDDEN)

        if User.objects.filter(username=username).exists():
            return Response("Пользователь с таким username уже существует", status=status.HTTP_400_BAD_REQUEST)
        
        user = User.objects.create(username=username, password=make_password(password))
        user_data = {'id': user.id, 'username': user.username}
        return Response(user_data, status=status.HTTP_200_OK)
    
    def destroy(self, request, pk=None):
        if not request.user.is_superuser:
            return Response("Недостаточно прав", status=status.HTTP_403_FORBIDDEN)
        
        user = User.objects.filter(id=pk).first()
        if not user:
            return Response("Пользователь не найден", status=status.HTTP_404_NOT_FOUND)
        
        # удаляем,если он есть
        user.delete()
        return Response("Пользователь успешно удалён", status=status.HTTP_200_OK)
