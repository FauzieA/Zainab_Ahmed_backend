from django.contrib import admin
from .models import ServiceConfiguration, AvailableSlot, BookingRecord

@admin.register(ServiceConfiguration)
class ServiceConfigurationAdmin(admin.ModelAdmin):
    list_display = ('title', 'price', 'currency', 'duration', 'updated_at')

@admin.register(AvailableSlot)
class AvailableSlotAdmin(admin.ModelAdmin):
    list_display = ('date_string', 'time_string', 'is_booked')
    list_filter = ('is_booked', 'date_string')
    search_fields = ('date_string', 'time_string')

@admin.register(BookingRecord)
class BookingRecordAdmin(admin.ModelAdmin):
    list_display = ('client_email', 'date_booked', 'time_booked', 'status', 'created_at')
    list_filter = ('status', 'date_booked')
    readonly_fields = ('booking_reference', 'created_at')