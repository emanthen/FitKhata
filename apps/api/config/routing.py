from django.urls import path

from attendance.consumers import GymFeedConsumer

websocket_urlpatterns = [
    path("ws/gym/<uuid:gym_id>/feed", GymFeedConsumer.as_asgi()),
]
