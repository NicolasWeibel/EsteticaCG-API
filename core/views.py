from django.http import HttpResponse


def health_check(request):
    # Retornamos un 200 OK sin contenido para minimizar el tráfico de red
    return HttpResponse(status=200)
