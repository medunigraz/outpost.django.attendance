from django.views.generic import TemplateView

from outpost.django.campusonline import models as co


class HoldingView(TemplateView):
    template_name = 'attendance/holding.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['room'] = co.Room.objects.get(pk=self.kwargs['room'])
        return context
