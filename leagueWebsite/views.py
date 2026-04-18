from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm

def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next') or '/'
            return HttpResponseRedirect(next_url)
    else:
        form = AuthenticationForm()
    
    next_url = request.POST.get('next') or request.GET.get('next') or '/'
    return render(request, 'login.html', {'form': form, 'next': next_url})

@login_required
def user_logout(request):

    logout(request)
    next_url = request.META.get('HTTP_REFERER', '/')

    return HttpResponseRedirect(next_url)
