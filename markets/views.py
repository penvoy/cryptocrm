from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework import status

from .models import Markets
# Create your views here.


class MarketView(APIView):
    """ добавление биржи в БД """
    @staticmethod
    def post(request: Request, *args, **kwargs):
        name = request.data.get('name')
        account = request.data.get('account')
        private_key = request.data.get('private_key')
        public_key = request.data.get('public_key')
        uid = request.data.get('uid')

        if name and (private_key or public_key):
            created = Markets.objects.create(
                name=name,
                private_key=private_key,
                public_key=public_key,
                uid=uid,
                account=account
            )
            return Response("Биржа добавлена", status=status.HTTP_200_OK)
        
        return Response("Неверные параметры", status=status.HTTP_400_BAD_REQUEST)
            

        
    def get(request: Request, *args, **kwargs):

        markets = Markets.objects.all()

        result = []
        for market in markets:
            response = {
                "id": market.id,
                "name": market.name,
                "account": market.account
            }
            result.append(response)

        return Response(result, status=status.HTTP_200_OK)
        