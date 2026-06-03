from django.urls import path
from . import views

app_name = 'pagos'

urlpatterns = [
    path('webhook/',  views.webhook,       name='webhook'),
    path('exitoso/',  views.pago_exitoso,  name='exitoso'),
    path('pendiente/', views.pago_pendiente, name='pendiente'),
    path('fallido/',  views.pago_fallido,  name='fallido'),
]
