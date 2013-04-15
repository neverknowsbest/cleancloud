from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from dedool_profile.models import UserProfile
from dedool_profile.forms import UserProfileForm


@login_required
def profile(request):
    """
    Edit or add auxiliary account information such as name, address, etc. This data goes into the
    UserProfile model, not the User model, which is only for authentication.
    """
    user = request.user

    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        profile = None

    if request.method == "POST":
        if not profile:
            form = UserProfileForm(request.POST)
        form = UserProfileForm(request.POST, instance=profile)

        if form.is_valid():
            form.save()
            return redirect('dedool_profile.views.edit_profile')
        else:
            return render(request, 'cleancloud/edit_profile.html',
                          {'user': user, 'profile': profile, 'error': form.errors})

    return render(request, 'cleancloud/edit_profile.html', {'user': user, 'profile': profile})

