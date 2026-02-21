from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

def user_login(request):

    if request.method == 'POST':

        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(username=username, password=password)

        if user:
            if user.is_active:
                login(request,user)
                return HttpResponseRedirect(reverse('home'))
            else:
                return HttpResponse("Account not active")
        else:
            return HttpResponse("Invalid login details supplied")

    else:

        return render(request,'registration/login.html',{})

@login_required
def user_logout(request):

    logout(request)

    return HttpResponseRedirect(reverse('home'))
