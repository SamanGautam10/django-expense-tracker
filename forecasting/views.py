from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .services import forecast

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def forecast_view(request):
    return Response(forecast(request.user))   # only ever reads request.user's expenses
