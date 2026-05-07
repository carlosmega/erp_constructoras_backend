"""
Django Admin configuration for User Management.

Provides admin interface for SystemUser and SecurityRole models with proper
password handling (hashed on save, separate change-password form).
"""

from django import forms
from django.contrib import admin
from django.contrib.auth.forms import (
    AdminPasswordChangeForm,
    ReadOnlyPasswordHashField,
)
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from apps.users.models import SecurityRole, SystemUser


@admin.register(SecurityRole)
class SecurityRoleAdmin(admin.ModelAdmin):
    list_display = ('securityroleid', 'name', 'description')
    search_fields = ('name', 'description')
    readonly_fields = ('securityroleid',)
    ordering = ('name',)

    fieldsets = (
        ('Role Information', {
            'fields': ('securityroleid', 'name', 'description')
        }),
    )


class SystemUserCreationForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput,
        help_text='Mínimo 8 caracteres.',
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput,
    )

    class Meta:
        model = SystemUser
        fields = ('emailaddress1', 'fullname', 'securityroleid', 'isdisabled')

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        if p1 and len(p1) < 8:
            raise forms.ValidationError('La contraseña debe tener al menos 8 caracteres.')
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class SystemUserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(
        label='Contraseña',
        help_text=(
            'Las contraseñas se guardan hasheadas, no es posible verlas. '
            'Puedes cambiarla usando <a href="../password/">este formulario</a>.'
        ),
    )

    class Meta:
        model = SystemUser
        fields = (
            'emailaddress1', 'fullname', 'password',
            'securityroleid', 'isdisabled',
        )


@admin.register(SystemUser)
class SystemUserAdmin(admin.ModelAdmin):
    form = SystemUserChangeForm
    add_form = SystemUserCreationForm
    change_password_form = AdminPasswordChangeForm

    list_display = (
        'emailaddress1',
        'fullname',
        'get_role_name',
        'isdisabled',
        'failedloginattempts',
        'lastlogindate',
        'createdon',
    )
    list_filter = ('isdisabled', 'securityroleid', 'createdon')
    search_fields = ('emailaddress1', 'fullname')
    ordering = ('fullname',)

    readonly_fields = (
        'systemuserid',
        'createdon',
        'modifiedon',
        'createdby',
        'modifiedby',
        'lastlogindate',
        'failedloginattempts',
    )

    fieldsets = (
        ('Authentication', {
            'fields': ('emailaddress1', 'password')
        }),
        ('Personal Information', {
            'fields': ('fullname',)
        }),
        ('Security & Role', {
            'fields': ('securityroleid', 'isdisabled')
        }),
        ('Login Information', {
            'fields': ('lastlogindate', 'failedloginattempts')
        }),
        ('Audit Information', {
            'fields': ('systemuserid', 'createdon', 'modifiedon', 'createdby', 'modifiedby'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        ('Authentication', {
            'fields': ('emailaddress1', 'password1', 'password2'),
        }),
        ('Personal Information', {
            'fields': ('fullname',),
        }),
        ('Security & Role', {
            'fields': ('securityroleid', 'isdisabled'),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = self.add_form
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    def get_urls(self):
        return [
            path(
                '<path:object_id>/password/',
                self.admin_site.admin_view(self.user_change_password),
                name='users_systemuser_password_change',
            ),
        ] + super().get_urls()

    def user_change_password(self, request, object_id, form_url=''):
        if not self.has_change_permission(request):
            raise PermissionDenied

        user = self.get_object(request, object_id)
        if user is None:
            raise Http404

        if request.method == 'POST':
            form = self.change_password_form(user, request.POST)
            if form.is_valid():
                form.save()
                self.message_user(
                    request,
                    f'Contraseña actualizada para {user.emailaddress1}.',
                )
                return HttpResponseRedirect(
                    reverse(
                        'admin:users_systemuser_change',
                        args=(user.pk,),
                    )
                )
        else:
            form = self.change_password_form(user)

        context = {
            **self.admin_site.each_context(request),
            'title': f'Cambiar contraseña: {user.emailaddress1}',
            'form': form,
            'is_popup': '_popup' in request.GET,
            'add': True,
            'change': False,
            'has_delete_permission': False,
            'has_change_permission': True,
            'has_absolute_url': False,
            'opts': self.model._meta,
            'original': user,
            'save_as': False,
            'show_save': True,
        }

        return TemplateResponse(
            request,
            'admin/auth/user/change_password.html',
            context,
        )

    def get_role_name(self, obj):
        return obj.role_name or '-'
    get_role_name.short_description = 'Role'
    get_role_name.admin_order_field = 'securityroleid__name'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.createdby = request.user
            obj.modifiedby = request.user
        else:
            obj.modifiedby = request.user
        super().save_model(request, obj, form, change)
